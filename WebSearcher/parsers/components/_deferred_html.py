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
"""

import re

from selectolax.lexbor import LexborNode as Node

from .ai_overview import _root_html

_RX_FRAGMENT = re.compile(
    r"""\{id:'([^']+)'\},function\(\)\{jsl\.dh\(this\.id,"([^"\\]*(?:\\.[^"\\]*)*)\"""",
    re.DOTALL,
)
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


def fill_deferred_html(scope: Node) -> list[Node]:
    """Fill each empty ``jsl.dh`` target inside ``scope``, returning the targets filled.

    Fragments run in document order, as in a browser, so a fragment can fill a
    placeholder that an earlier fragment created.
    """
    filled: list[Node] = []
    for target_id, body in _RX_FRAGMENT.findall(_root_html(scope)):
        target = scope.css_first(f'[id="{target_id}"]')
        if target is None or (target.inner_html or "").strip():
            continue
        target.inner_html = unescape_js_string(body)
        filled.append(target)
    return filled
