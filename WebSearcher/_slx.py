"""A small bs4-compatible adapter over selectolax (lexbor).

Plan 026: replace the lxml+BeautifulSoup parse/query layer with selectolax for
speed. The pipeline passes a single parsed tree through ~50 parsers, the
classifier, and the extractor, all written against a subset of the bs4 `Tag` API.
Rather than rewrite every call site at once, this module wraps selectolax `Node`s
in a `SoupNode` that emulates that bs4 subset, so `make_soup` can return it and
the existing code keeps working. Hot paths are then moved to native selectolax.

This module is in transition (plan 026's "native rewrite" follow-up):
- ``SoupNode`` (the bs4-compatible class) remains in place during the parser
  migration so unmigrated call sites keep working.
- Native parsers escape the wrapper via ``cmpt.raw`` (the underlying selectolax
  ``Node``) and call this module's public ``get_text``/``class_tokens``/
  ``find_text``/``reparse_fragment``/``node_string`` helpers for the bs4-faithful
  bits that don't translate cleanly to native selectolax (text walker, class
  parsing, etc.). When all parsers are native, the class is removed and
  ``make_soup`` returns ``Node`` directly.

Faithfulness rules pinned empirically against bs4+lxml (so the snapshot suite
stays byte-identical):

- ``find``/``find_all`` match in document (pre-order) order; ``find`` returns the
  first match. Matching is descendants-only (not self), except the document root.
- class attribute query semantics: a single token matches by membership; a
  multi-token string matches the exact ordered class string; a list matches any
  token (OR). Mirrors bs4.
- ``get_text`` skips ``<script>``/``<style>``/``<template>`` text (bs4+lxml does),
  and otherwise reproduces bs4's separator/strip/join behavior exactly.
- ``.attrs`` exposes ``class`` as a list (and ``rel`` likewise), valueless attrs
  as ``""`` -- matching bs4.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from selectolax.parser import HTMLParser, Node

# Text under these never contributes to get_text in bs4+lxml.
_SKIP_TEXT_TAGS = {"script", "style", "template"}
# bs4 multi-valued attributes (returned/matched as token lists).
_MULTI_ATTRS = {"class", "rel"}


def _is_element(raw: Node) -> bool:
    tag = raw.tag
    return bool(tag) and not tag.startswith("-")


def _child_nodes(raw: Node, include_text: bool) -> list[Node]:
    return list(raw.iter(include_text=include_text))


def _walk(raw: Node, include_text: bool) -> Iterator[Node]:
    """Pre-order DFS over descendants (excludes ``raw`` itself)."""
    for child in raw.iter(include_text=include_text):
        yield child
        yield from _walk(child, include_text)


def _node_text(raw: Node) -> str:
    """Raw text of a text node (whitespace preserved)."""
    return raw.text(deep=False)


def _iter_text_fragments(raw: Node) -> Iterator[str]:
    """Text fragments in document order, skipping script/style/template subtrees.

    Includes ``raw``'s own text if it is itself a text node.
    """
    if raw.tag == "-text":
        yield _node_text(raw)
        return
    for child in raw.iter(include_text=True):
        t = child.tag
        if t == "-text":
            yield _node_text(child)
        elif t in _SKIP_TEXT_TAGS or t.startswith("-"):
            continue
        else:
            yield from _iter_text_fragments(child)


def _node_string(raw: Node) -> str | None:
    """bs4 ``Tag.string``: the single string child (recursing through a lone tag
    child), else None when the node has zero or multiple children."""
    children = list(raw.iter(include_text=True))
    if len(children) != 1:
        return None
    c = children[0]
    if c.tag == "-text":
        return _node_text(c)
    if c.tag.startswith("-"):
        return None
    return _node_string(c)


def _string_matches(text: str, string: Any) -> bool:
    if string is True:
        return bool(text)
    if isinstance(string, re.Pattern):
        return bool(string.search(text))
    return text == string


def _class_tokens(raw: Node) -> list[str]:
    cls = raw.attributes.get("class")
    return cls.split() if cls else []


def _attr_value_matches(raw: Node, key: str, query: Any) -> bool:
    if key == "class":
        tokens = _class_tokens(raw)
        if isinstance(query, (list, tuple, set)):
            return any(q in tokens for q in query)
        if isinstance(query, re.Pattern):
            return any(query.search(t) for t in tokens) or bool(query.search(" ".join(tokens)))
        q = str(query)
        if " " in q.strip():
            return " ".join(tokens) == " ".join(q.split())
        return q in tokens

    val = raw.attributes.get(key)
    if val is None:
        # Distinguish "attribute absent" from "valueless attribute" (bs4 "").
        if key not in raw.attributes:
            return False
        val = ""
    if isinstance(query, (list, tuple, set)):
        return val in query
    if isinstance(query, re.Pattern):
        return bool(query.search(val))
    if query is True:
        return True
    return val == str(query)


def _matches(raw: Node, name: Any, attrs: dict, string: Any) -> bool:
    if not _is_element(raw):
        return False
    if name is not None and name is not True:  # True = "any tag" (bs4)
        if isinstance(name, (list, tuple, set)):
            if raw.tag not in name:
                return False
        elif raw.tag != name:
            return False
    for key, query in attrs.items():
        if not _attr_value_matches(raw, key, query):
            return False
    if string is not None:
        if name is None and not attrs:
            # bs4 find(string=...) with no tag filter: search the element's text.
            text = "".join(_iter_text_fragments(raw))
            if string is True:
                return bool(text)
            if isinstance(string, re.Pattern):
                return bool(string.search(text))
            return text == string
        # bs4 find(name, string=...): match the tag's `.string` (single child).
        s = _node_string(raw)
        if string is True:
            return s is not None
        if isinstance(string, re.Pattern):
            return s is not None and bool(string.search(s))
        return s == string
    return True


def _normalize_attrs(name, attrs, kwargs) -> tuple[Any, dict]:
    """Merge bs4-style (name, attrs={}, **kwargs) into (name, attr-dict)."""
    merged: dict[str, Any] = dict(attrs) if attrs else {}
    for k, v in kwargs.items():
        if k == "class_":
            merged["class"] = v
        elif k in ("recursive", "limit", "string"):
            continue
        else:
            merged[k] = v
    return name, merged


def _css_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_css(name: Any, attrs: dict) -> str | None:
    """Translate a bs4 (name, attrs) query into a single CSS selector for the
    lexbor engine, or None when the query has semantics CSS can't express exactly
    (regex values, attr/class lists -> OR, multi-token class exact-match,
    name lists). Those fall back to the Python matcher so output stays identical.

    Uses ``[class~="x"]`` for class tokens -- provably equivalent to bs4
    ``class_="x"`` token membership (validated against the corpus).
    """
    if isinstance(name, (list, tuple, set)) or callable(name):
        return None
    tag = "*" if (name is None or name is True) else name
    parts = [tag]
    for key, val in attrs.items():
        if isinstance(val, re.Pattern) or isinstance(val, (list, tuple, set)):
            return None
        if key == "class":
            v = str(val)
            if " " in v.strip():  # multi-token = exact ordered match, not CSS AND
                return None
            parts.append(f'[class~="{_css_escape(v)}"]')
        elif val is True:
            parts.append(f"[{key}]")
        else:
            parts.append(f'[{key}="{_css_escape(str(val))}"]')
    return "".join(parts)


class SoupNode:
    """bs4-`Tag`-compatible wrapper around a selectolax ``Node``."""

    __slots__ = ("_raw", "_parser", "_is_root")

    def __init__(self, raw: Node, parser: HTMLParser | None = None, is_root: bool = False):
        self._raw = raw
        self._parser = parser  # keep the owning tree alive
        self._is_root = is_root

    # -- construction helpers --------------------------------------------------
    def _wrap(self, raw: Node | None) -> SoupNode | None:
        if raw is None:
            return None
        return SoupNode(raw, self._parser)

    # -- identity / truthiness -------------------------------------------------
    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"SoupNode<{self._raw.tag}>"

    def __str__(self) -> str:
        if self._raw.tag == "-text":
            return _node_text(self._raw)
        return self._raw.html or ""

    # -- node identity ---------------------------------------------------------
    @property
    def name(self) -> str | None:
        return self._raw.tag if _is_element(self._raw) else None

    @property
    def raw(self) -> Node:
        return self._raw

    @property
    def mem_id(self) -> int:
        """Stable identity of the underlying DOM node (survives re-wrapping and
        detachment). Used for document-position bookkeeping where bs4 relied on
        Python ``id()`` of a stable Tag object."""
        return self._raw.mem_id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SoupNode) and self._raw.mem_id == other._raw.mem_id

    def __hash__(self) -> int:
        return self._raw.mem_id

    # -- attributes ------------------------------------------------------------
    @property
    def attrs(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in self._raw.attributes.items():
            if k in _MULTI_ATTRS:
                out[k] = (v or "").split()
            else:
                out[k] = v if v is not None else ""
        return out

    def get(self, key: str, default: Any = None) -> Any:
        if key not in self._raw.attributes:
            return default
        v = self._raw.attributes.get(key)
        if key in _MULTI_ATTRS:
            return (v or "").split()
        return v if v is not None else ""

    def has_attr(self, key: str) -> bool:
        return key in self._raw.attributes

    def __getitem__(self, key: str) -> Any:
        if key not in self._raw.attributes:
            raise KeyError(key)
        v = self._raw.attributes.get(key)
        if key in _MULTI_ATTRS:
            return (v or "").split()
        return v if v is not None else ""

    def __contains__(self, key: str) -> bool:
        # bs4 Tag.__contains__ tests child membership, but the codebase only uses
        # `"attrs" in c` (always falsey on a real tag) -- emulate by attr key.
        return key in self._raw.attributes

    # -- text ------------------------------------------------------------------
    def get_text(self, separator: str = "", strip: bool = False) -> str:
        frags = _iter_text_fragments(self._raw)
        if strip:
            parts = [s for s in (f.strip() for f in frags) if s]
        else:
            parts = list(frags)
        return separator.join(parts)

    @property
    def text(self) -> str:
        return self.get_text()

    @property
    def strings(self) -> Iterator[str]:
        yield from _iter_text_fragments(self._raw)

    @property
    def stripped_strings(self) -> Iterator[str]:
        for s in _iter_text_fragments(self._raw):
            s = s.strip()
            if s:
                yield s

    # -- navigation ------------------------------------------------------------
    @property
    def parent(self) -> SoupNode | None:
        return self._wrap(self._raw.parent)

    @property
    def children(self) -> Iterator[SoupNode]:
        for child in self._raw.iter(include_text=True):
            wrapped = self._wrap(child)
            if wrapped is not None:
                yield wrapped

    @property
    def contents(self) -> list[SoupNode]:
        return list(self.children)

    @property
    def descendants(self) -> Iterator[SoupNode]:
        for d in _walk(self._raw, include_text=True):
            wrapped = self._wrap(d)
            if wrapped is not None:
                yield wrapped

    def _sibling_list(self) -> list[Node]:
        parent = self._raw.parent
        if parent is None:
            return []
        return list(parent.iter(include_text=True))

    def _sibling_index(self, sibs: list[Node]) -> int:
        for i, s in enumerate(sibs):
            if s is self._raw:
                return i
        return -1

    @property
    def next_sibling(self) -> SoupNode | None:
        sibs = self._sibling_list()
        i = self._sibling_index(sibs)
        return self._wrap(sibs[i + 1]) if 0 <= i < len(sibs) - 1 else None

    @property
    def previous_sibling(self) -> SoupNode | None:
        sibs = self._sibling_list()
        i = self._sibling_index(sibs)
        return self._wrap(sibs[i - 1]) if i > 0 else None

    @property
    def next_siblings(self) -> Iterator[SoupNode]:
        sibs = self._sibling_list()
        i = self._sibling_index(sibs)
        if i < 0:
            return
        for s in sibs[i + 1 :]:
            w = self._wrap(s)
            if w is not None:
                yield w

    # -- search ----------------------------------------------------------------
    def _text_nodes(self, recursive: bool) -> Iterator[Node]:
        if recursive:
            for n in _walk(self._raw, include_text=True):
                if n.tag == "-text":
                    yield n
        else:
            for n in self._raw.iter(include_text=True):
                if n.tag == "-text":
                    yield n

    def _candidates(self, recursive: bool) -> Iterator[Node]:
        if self._is_root and _is_element(self._raw):
            yield self._raw
        if recursive:
            yield from _walk(self._raw, include_text=False)
        else:
            yield from self._raw.iter(include_text=False)

    def _css_query(self, name: Any, merged: dict, string: Any, recursive: bool) -> str | None:
        """CSS selector for the fast lexbor path, or None to use the Python matcher."""
        if string is not None or not recursive:
            return None
        return _build_css(name, merged)

    def find(self, name: Any = None, attrs: dict | None = None, recursive: bool = True,
             string: Any = None, **kwargs) -> SoupNode | None:
        if callable(name):  # bs4 callable filter: predicate over each tag
            for raw in self._candidates(recursive):
                w = self._wrap(raw)
                if w is not None and w.name is not None and name(w):
                    return w
            return None
        name, merged = _normalize_attrs(name, attrs, kwargs)
        string = kwargs.get("string", string)
        if string is not None and name is None and not merged:
            # bs4 find(string=...): scan text nodes directly (O(text), not
            # O(elements x subtree) -- the latter made has_captcha quadratic).
            for tnode in self._text_nodes(recursive):
                if _string_matches(_node_text(tnode), string):
                    return self._wrap(tnode)
            return None
        css = self._css_query(name, merged, string, recursive)
        if css is not None:
            if self._is_root and _matches(self._raw, name, merged, None):
                return self._wrap(self._raw)
            self_id = self._raw.mem_id
            for raw in self._raw.css(css):  # css matches self too; bs4 = descendants only
                if raw.mem_id != self_id:
                    return self._wrap(raw)
            return None
        for raw in self._candidates(recursive):
            if _matches(raw, name, merged, string):
                return self._wrap(raw)
        return None

    def find_all(self, name: Any = None, attrs: dict | None = None, recursive: bool = True,
                 limit: int | None = None, string: Any = None, **kwargs) -> list[SoupNode]:
        out: list[SoupNode] = []
        if callable(name):  # bs4 callable filter
            for raw in self._candidates(recursive):
                w = self._wrap(raw)
                if w is not None and w.name is not None and name(w):
                    out.append(w)
                    if limit and len(out) >= limit:
                        break
            return out
        name, merged = _normalize_attrs(name, attrs, kwargs)
        string = kwargs.get("string", string)
        if string is not None and name is None and not merged:
            for tnode in self._text_nodes(recursive):
                if _string_matches(_node_text(tnode), string):
                    out.append(SoupNode(tnode, self._parser))
                    if limit and len(out) >= limit:
                        break
            return out
        css = self._css_query(name, merged, string, recursive)
        if css is not None:
            self_id = self._raw.mem_id
            seen: set[int] = {self_id}  # exclude self: bs4 searches descendants only
            if self._is_root and _matches(self._raw, name, merged, None):
                out.append(SoupNode(self._raw, self._parser))
            for raw in self._raw.css(css):
                if raw.mem_id in seen:
                    continue
                seen.add(raw.mem_id)
                out.append(SoupNode(raw, self._parser))
                if limit and len(out) >= limit:
                    break
            return out
        for raw in self._candidates(recursive):
            if _matches(raw, name, merged, string):
                out.append(SoupNode(raw, self._parser))
                if limit and len(out) >= limit:
                    break
        return out

    findAll = find_all

    def find_parent(self, name: Any = None, attrs: dict | None = None,
                    **kwargs) -> SoupNode | None:
        name, merged = _normalize_attrs(name, attrs, kwargs)
        string = kwargs.get("string")
        raw = self._raw.parent
        while raw is not None:
            if _matches(raw, name, merged, string):
                return self._wrap(raw)
            raw = raw.parent
        return None

    # -- CSS (native selectolax) ----------------------------------------------
    def select(self, css: str) -> list[SoupNode]:
        return [SoupNode(n, self._parser) for n in self._raw.css(css)]

    def select_one(self, css: str) -> SoupNode | None:
        return self._wrap(self._raw.css_first(css))

    # -- mutation --------------------------------------------------------------
    def extract(self) -> SoupNode:
        """Detach this subtree from its tree and return it (bs4 semantics).

        ``remove()`` detaches the node from the source tree while keeping it alive
        and queryable, with its ``mem_id`` unchanged -- so document-position
        bookkeeping captured before extraction still resolves it, exactly as bs4's
        stable Tag identity did.
        """
        self._raw.remove(recursive=False)  # recursive=True would prune descendants
        self._is_root = False
        return self

    def decompose(self) -> None:
        self._raw.decompose()

    # -- bs4 `.div` / `.span` first-descendant access --------------------------
    def __getattr__(self, name: str) -> Any:
        # Only fires for attributes not in __slots__/methods. bs4 exposes
        # `tag.<name>` as the first descendant element of that tag. Restrict to
        # plain tag names so missing methods (e.g. find_parent) error clearly
        # instead of being silently treated as a tag lookup.
        if "_" in name or not name.isalpha():
            raise AttributeError(name)
        return self.find(name)

    # -- copy ------------------------------------------------------------------
    def __copy__(self) -> SoupNode:
        return _reparse_fragment(self._raw.html or "")


def is_tag(obj: Any) -> bool:
    """Replacement for ``isinstance(x, bs4.element.Tag)`` -- True for an element
    SoupNode (not a text/comment node)."""
    return isinstance(obj, SoupNode) and obj.name is not None


def _reparse_fragment(html: str) -> SoupNode:
    """Parse a fragment and return its top element as an independent SoupNode."""
    parser = HTMLParser(html)
    body = parser.body
    top = None
    if body is not None:
        for child in body.iter(include_text=False):
            top = child
            break
    if top is None:
        top = parser.root
    return SoupNode(top, parser)


def make_soup_slx(html: str | bytes | SoupNode) -> SoupNode:
    if isinstance(html, SoupNode):
        return html
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    parser = HTMLParser(html)
    return SoupNode(parser.root, parser, is_root=True)


# Public function-form helpers for the native-rewrite migration -----------------
# Parsers being rewritten escape SoupNode via ``cmpt.raw`` and call these helpers
# directly. When all parsers are native and SoupNode is removed, these become the
# only module surface.


def get_text(node: Node | None, separator: str = "", strip: bool = False) -> str | None:
    """bs4-faithful Tag.get_text: walk descendants, skip script/style/template,
    join text fragments by ``separator``. When ``strip=True``, strip each fragment
    AND drop empties before joining (selectolax native ``Node.text(strip=True)``
    keeps empties, producing leading/trailing/extra separators — this differs and
    breaks downstream parsing in the slug / link-key sites).

    Returns ``None`` for a ``None`` input (matching ``utils.get_text``'s
    null-handling convention so parsers can chain ``css_first`` + ``get_text``
    without checking for ``None`` mid-chain)."""
    if node is None:
        return None
    frags = _iter_text_fragments(node)
    if strip:
        parts = [s for s in (f.strip() for f in frags) if s]
    else:
        parts = list(frags)
    return separator.join(parts)


def next_sibling(node: Node, include_text: bool = True) -> Node | None:
    """Next sibling in document order (text nodes included by default, matching
    bs4 ``.next_sibling``). selectolax's native ``.next`` may skip text nodes."""
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


def walk_descendants(node: Node, include_text: bool = False) -> Iterator[Node]:
    """Pre-order DFS over descendants in document order, EXCLUDING ``node`` itself.

    Use this instead of selectolax ``node.traverse(...)``, which walks the
    entire document from ``node``'s position forward (not just its subtree),
    and instead of ``node.css(...)``, which groups results by comma-branch
    rather than preserving document order."""
    return _walk(node, include_text=include_text)


def has_text(node: Node | None) -> bool:
    """True if ``node``'s subtree contains at least one non-whitespace text
    fragment (short-circuits at the first hit). The replacement for the
    ``utils.filter_empty_divs`` element-keep predicate."""
    if node is None:
        return False
    for s in _iter_text_fragments(node):
        if s and not s.isspace():
            return True
    return False


def class_tokens(node: Node) -> list[str]:
    """Return the ``class`` attribute as a list of tokens (selectolax stores it
    as a single whitespace-separated string)."""
    return _class_tokens(node)


def node_string(node: Node) -> str | None:
    """bs4 ``Tag.string`` semantics: single direct text-node child's text, or
    recurse through a single tag child. ``None`` when the node has zero or
    multiple element/text children. Used by the one ``find(name_list, string=True)``
    call site in ``knowledge.py``."""
    return _node_string(node)


def find_text(node: Node, pattern: re.Pattern[str]) -> Node | None:
    """First descendant text node whose content matches ``pattern``.

    bs4 ``find(string=re.compile(...))`` with no tag filter. Scans text nodes
    directly (O(text), not O(elements x subtree) — the latter made
    ``has_captcha`` quadratic, see plan 023/026)."""
    for n in node.traverse(include_text=True):
        if n.tag == "-text" and pattern.search(n.text(deep=False) or ""):
            return n
    return None


def reparse_fragment(node: Node) -> Node:
    """Re-parse ``node``'s outer HTML into an independent tree and return its
    top element. Emulates bs4 ``copy.copy(tag)`` for the notices.py mutation
    pattern, where a parser needs to ``.extract()`` from a clone without
    mutating the source tree."""
    parser = HTMLParser(node.html or "")
    body = parser.body
    if body is None:
        return parser.root
    for child in body.iter(include_text=False):
        return child
    return parser.root


def make_soup_native(html: str | bytes | Node) -> Node:
    """``make_soup`` of the post-migration world: returns a native selectolax
    ``Node`` (the ``<html>`` root). Used by tests and by parsers being migrated;
    becomes ``make_soup`` proper once ``SoupNode`` is removed."""
    if isinstance(html, Node):
        return html
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    return HTMLParser(html).root
