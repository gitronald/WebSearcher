"""Native selectolax helpers for the parse pipeline.

After the native rewrite (plan 026), the bs4-compatible ``SoupNode`` adapter
that originally lived here is gone -- every parser, classifier, and extractor
calls selectolax's ``HTMLParser`` / ``Node`` API directly. This module hosts
the small set of helpers that don't translate cleanly to a bare ``.css(...)``
call:

- bs4-faithful ``get_text`` (strip-then-drop-empties; skip script/style/template)
  -- selectolax native ``Node.text(strip=True)`` keeps empty fragments, which
  silently breaks slug and link-key parsers downstream.
- ``class_tokens`` -- ``class`` is a whitespace-separated string in selectolax,
  not a list as in bs4.
- ``walk_descendants`` -- pre-order DFS over a node's subtree.
  Necessary because ``Node.traverse(...)`` walks the *entire document* from
  this point forward, not just the subtree.
- ``subtree_first`` / ``subtree_css`` -- descendants-only queries (bs4
  ``find``/``find_all`` semantics; selectolax ``.css`` matches self too).
- ``next_sibling`` / ``previous_sibling`` / ``next_siblings`` -- text-inclusive,
  matching bs4 (selectolax ``.next`` may skip text nodes).
- ``node_string`` -- bs4 ``Tag.string`` semantics (single-string-child, recursing
  through a single tag child). Used by the one ``find(name_list, string=True)``
  call site in ``knowledge.py``.
- ``reparse_fragment`` -- re-parse a node's HTML into an independent tree, for
  the ``copy.copy(tag)`` pattern that the notices parser relies on.
- ``make_soup`` -- ``HTMLParser(html).root`` with bytes handling.
"""

from __future__ import annotations

from collections.abc import Iterator

from selectolax.lexbor import LexborHTMLParser as HTMLParser
from selectolax.lexbor import LexborNode as Node

# Text under these never contributes to get_text (matches bs4+lxml).
_SKIP_TEXT_TAGS = frozenset({"script", "style", "template"})


def _node_text(raw: Node) -> str:
    """Raw text of a text node (whitespace preserved)."""
    return raw.text(deep=False)


def _iter_text_fragments(raw: Node) -> Iterator[str]:
    """Text fragments in document order, skipping script/style/template subtrees."""
    if raw.tag == "-text":
        yield _node_text(raw)
        return
    # ``Node.iter`` is already a Cython generator, so it supports ``next()``
    # directly -- no extra ``iter()`` wrap needed.
    stack: list[Iterator[Node]] = [raw.iter(include_text=True)]
    while stack:
        child = next(stack[-1], None)
        if child is None:
            stack.pop()
            continue
        t = child.tag
        if t == "-text":
            yield _node_text(child)
        elif t is None or t in _SKIP_TEXT_TAGS or t.startswith("-"):
            continue
        else:
            stack.append(child.iter(include_text=True))


def node_string(node: Node) -> str | None:
    """bs4 ``Tag.string`` semantics: the single string child's text (recursing
    through a single tag child); ``None`` when the node has zero or multiple
    children."""
    children = list(node.iter(include_text=True))
    if len(children) != 1:
        return None
    c = children[0]
    tag = c.tag
    if tag == "-text":
        return _node_text(c)
    if tag is None or tag.startswith("-"):
        return None
    return node_string(c)


def make_soup(html: str | bytes | Node) -> Node:
    """Parse HTML and return its root ``<html>`` ``Node``.

    Accepts an existing ``Node`` and returns it unchanged. Bytes are decoded as
    UTF-8 (replace errors)."""
    if isinstance(html, Node):
        return html
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    root = HTMLParser(html).root
    if root is None:
        raise ValueError("could not parse HTML into a root node")
    return root


def get_text(node: Node | None, separator: str = "", strip: bool = False) -> str | None:
    """bs4-faithful ``Tag.get_text``: skip script/style/template, join text
    fragments by ``separator``. When ``strip=True``, strip each fragment AND
    drop empties before joining (selectolax native ``Node.text(strip=True)``
    keeps empties, producing leading/trailing/extra separators -- this differs
    and breaks downstream parsing in the slug / link-key sites).

    Returns ``None`` for a ``None`` input so parsers can chain ``css_first``
    + ``get_text``."""
    if node is None:
        return None
    # Fast path: selectolax's native C ``text()`` is byte-identical to the Python
    # fragment walker below EXCEPT for two differences -- native includes
    # script/style/template text and native keeps empty fragments (the
    # ``strip=True`` walker drops them). On the script/style/template side, the
    # walker skips those tags only as *descendants* (``_iter_text_fragments``
    # does not special-case a root that is itself one), so two guards are needed:
    # ``node.tag not in _SKIP_TEXT_TAGS`` (root) and the ``css_first`` probe
    # (descendants). The empty-fragment difference vanishes when ``separator`` is
    # empty (empties add nothing to a ""-join, so kept-vs-dropped is invisible)
    # or ``strip`` is False (both keep empties identically). Together these
    # cover ~95% of calls on this corpus; the one remaining case (``strip=True``
    # with a non-empty separator) keeps the Python walker. Verified
    # byte-identical over the full fixture corpus (315k nodes).
    if (
        (separator == "" or not strip)
        and node.tag not in _SKIP_TEXT_TAGS
        and node.css_first("script,style,template") is None
    ):
        return node.text(deep=True, separator=separator, strip=strip)
    frags = _iter_text_fragments(node)
    if strip:
        parts = [s for s in (f.strip() for f in frags) if s]
    else:
        parts = list(frags)
    return separator.join(parts)


def has_text(node: Node | None) -> bool:
    """True if ``node``'s subtree contains at least one non-whitespace text
    fragment (short-circuits)."""
    if node is None:
        return False
    for s in _iter_text_fragments(node):
        if s and not s.isspace():
            return True
    return False


def class_tokens(node: Node) -> list[str]:
    """Return the ``class`` attribute as a list of tokens (selectolax stores it
    as a single whitespace-separated string). Uses ``node.attrs`` (a view) so
    no dict is allocated per call."""
    cls = node.attrs.get("class")
    return cls.split() if cls else []


def reparse_fragment(node: Node) -> Node:
    """Re-parse ``node``'s outer HTML into an independent tree and return its
    top element. Emulates bs4 ``copy.copy(tag)`` for ``notices.py``."""
    parser = HTMLParser(node.html or "")
    root = parser.root
    if root is None:
        raise ValueError("could not reparse fragment into a root node")
    body = parser.body
    if body is None:
        return root
    for child in body.iter(include_text=False):
        return child
    return root


def subtree_first(node: Node, css: str) -> Node | None:
    """``node.css_first(css)`` excluding ``node`` itself.

    Selectolax ``.css`` matches ``node`` too if it matches the selector; bs4's
    ``find``/``find_all`` are descendants-only. Parsers that take a component
    root often need descendants-only semantics -- when the component itself
    happens to match an inner selector (e.g. ``cmpt`` is a ``div.VkpGBb`` and
    the parser searches ``div.VkpGBb`` for inner businesses), self-inclusion
    silently doubles up the wrapper as the first result."""
    self_id = node.mem_id
    for n in node.css(css):
        if n.mem_id != self_id:
            return n
    return None


def subtree_css(node: Node, css: str) -> list[Node]:
    """``node.css(css)`` excluding ``node`` itself (see ``subtree_first``)."""
    self_id = node.mem_id
    return [n for n in node.css(css) if n.mem_id != self_id]


def walk_descendants(node: Node) -> Iterator[Node]:
    """Pre-order element descendants of ``node`` in document order, excluding
    ``node`` itself. Backed by ``node.css('*')`` (one C-level walk) -- safer
    than ``traverse`` (whole-document) and ``css(comma)`` (branch-grouped)."""
    self_id = node.mem_id
    return (n for n in node.css("*") if n.mem_id != self_id)


def next_sibling(node: Node, include_text: bool = True) -> Node | None:
    """Next sibling in document order (text nodes included by default, matching
    bs4 ``.next_sibling``). Selectolax's native ``.next`` may skip text nodes."""
    parent = node.parent
    if parent is None:
        return None
    sibs = list(parent.iter(include_text=include_text))
    node_id = node.mem_id
    for i, sib in enumerate(sibs):
        if sib.mem_id == node_id and i + 1 < len(sibs):
            return sibs[i + 1]
    return None


def previous_sibling(node: Node, include_text: bool = True) -> Node | None:
    """Previous sibling (text-inclusive, matching bs4 ``.previous_sibling``)."""
    parent = node.parent
    if parent is None:
        return None
    sibs = list(parent.iter(include_text=include_text))
    node_id = node.mem_id
    for i, sib in enumerate(sibs):
        if sib.mem_id == node_id and i > 0:
            return sibs[i - 1]
    return None


def next_siblings(node: Node, include_text: bool = True) -> Iterator[Node]:
    """All next siblings (bs4 ``.next_siblings`` generator)."""
    parent = node.parent
    if parent is None:
        return
    sibs = list(parent.iter(include_text=include_text))
    node_id = node.mem_id
    found = False
    for sib in sibs:
        if found:
            yield sib
        elif sib.mem_id == node_id:
            found = True
