"""Fill a component's deferred HTML before its parser reads it.

Google ships much of a page as inline ``jsl.dh(id, html)`` calls that a browser
runs to fill empty placeholders: carousel cards, collapsed topic panels, video
key moments. A capture that never runs JavaScript holds those fragments only as
script text, so a parser would see the placeholders and none of their links.

A parser opts in by filling the subtree it wants. Filling a whole page does not
work: fragments also hold feedback dialogs, share menus, and People Also Ask
answers, which the generic parsers would read as the component's own content.

A browser capture has already run the calls, so a target that holds content is
left alone rather than reset to its original markup.

The calls are read by their arguments, not by the script around them, since the
wrapper varies by page and date: ``window.jsl.dh('id',"html")`` and
``{id:'id'},function(){jsl.dh(this.id,'html')``, in either quote style. A call this
cannot read is counted, and ``parse_serp`` reports both counts in its features, so a
format change shows up as a drop in the share read rather than as missing results.
"""

import re
from functools import lru_cache
from typing import NamedTuple

from selectolax.lexbor import LexborNode as Node

from ._common import root_html

# No leading \b: a literal prefix lets the scan skip ahead, which is most of its cost on a page.
_RX_CALL = re.compile(r"jsl\.dh\(\s*")
_RX_STRING = re.compile(r"""'[^'\\]*(?:\\.[^'\\]*)*'|"[^"\\]*(?:\\.[^"\\]*)*\"""", re.DOTALL)
_RX_COMMA = re.compile(r"\s*,\s*")
_THIS_ID = "this.id"
# The id a ``this.id`` call runs with: the object just before its function.
_RX_THIS_ID = re.compile(
    r"""\bid:\s*['"]([^'"]+)['"]\s*\}\s*,\s*function\(\)\s*\{\s*(?:window\.)?$"""
)
_THIS_ID_LOOKBACK = 300
_RX_JS_ESCAPE = re.compile(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|[\s\S])")
_RX_SURROGATE = re.compile("[\ud800-\udfff]")
_JS_CONTROL_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def _js_unescape_match(match: re.Match[str]) -> str:
    code = match.group(1)
    if len(code) > 1:
        return chr(int(code[1:], 16))
    return _JS_CONTROL_ESCAPES.get(code, code)


def unescape_js_string(text: str) -> str:
    """Decode the body of a double-quoted JavaScript string literal."""
    decoded = _RX_JS_ESCAPE.sub(_js_unescape_match, text)
    if _RX_SURROGATE.search(decoded):
        # An astral character is written as a pair of \uXXXX escapes.
        decoded = decoded.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    return decoded


class DeferredCalls(NamedTuple):
    """The ``jsl.dh`` calls of a page: how many, and the ``(id, body)`` of each one read."""

    n_calls: int
    fragments: tuple[tuple[str, str], ...]


def _read_call(html: str, start: int, end: int) -> tuple[str, str] | None:
    """The target id and still-escaped body of the call whose arguments start at ``end``."""
    if html.startswith(_THIS_ID, end):
        owner = _RX_THIS_ID.search(html, max(0, start - _THIS_ID_LOOKBACK), start)
        if owner is None:
            return None
        target_id = owner.group(1)
        end += len(_THIS_ID)
    else:
        literal = _RX_STRING.match(html, end)
        if literal is None:
            return None
        target_id = unescape_js_string(literal.group()[1:-1])
        end = literal.end()
    comma = _RX_COMMA.match(html, end)
    body = _RX_STRING.match(html, comma.end()) if comma is not None else None
    return (target_id, body.group()[1:-1]) if body is not None and target_id else None


@lru_cache(maxsize=1)
def read_deferred_calls(html: str) -> DeferredCalls:
    """Every ``jsl.dh`` call in a page's markup, in document order.

    Cached for the one page being parsed, since each parser fills its own subtree.
    """
    n_calls = 0
    fragments: list[tuple[str, str]] = []
    for match in _RX_CALL.finditer(html):
        n_calls += 1
        fragment = _read_call(html, match.start(), match.end())
        if fragment is not None:
            fragments.append(fragment)
    return DeferredCalls(n_calls, tuple(fragments))


def fill_deferred_html(scope: Node, containing: str | None = None) -> list[Node]:
    """Fill each empty ``jsl.dh`` target inside ``scope``, returning the targets filled.

    Fragments run in document order, as in a browser, so a fragment can fill a
    placeholder that an earlier fragment created. ``containing`` limits the fill to
    fragments whose source holds that text, for a parser that wants one kind.
    """
    filled: list[Node] = []
    for target_id, body in read_deferred_calls(root_html(scope)).fragments:
        if containing is not None and containing not in body:
            continue
        target = scope.css_first(f'[id="{target_id}"]')
        if target is None or (target.inner_html or "").strip():
            continue
        target.inner_html = unescape_js_string(body)
        filled.append(target)
    return filled
