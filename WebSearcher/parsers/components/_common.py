"""Shared helpers for component parsers.

Hosts the link-extraction helpers that several parsers each kept a near-identical
private copy of before plan 028. One parameterized ``parse_alink`` covers the
small, documented behavior differences (text separator, ``data-url`` fallback)
via explicit arguments.
"""

from collections.abc import Iterable
from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text, is_element, is_hidden


def mark_hidden_row(parsed: dict[str, Any], node: Node | None) -> dict[str, Any]:
    """Record ``visible=False`` in a result row's ``details`` when ``node`` is
    hidden (the inline ``display:none`` lazy-render pattern; see
    :func:`._slx.is_hidden`).

    ``visible`` is recorded *only when False* (the default is visible), so this
    is a no-op for shown rows. A row with no content payload gains a
    metadata-only ``details`` (``type="item"``); a content row gets the flag as
    a sibling key. Call **after** the row's content ``details`` is built so the
    flag is not overwritten.
    """
    if is_hidden(node):
        details = parsed.get("details")
        if isinstance(details, dict):
            details["visible"] = False
        else:
            parsed["details"] = {"type": "item", "visible": False}
    return parsed


def mark_timestamp_row(parsed: dict[str, Any], timestamp: str | None) -> dict[str, Any]:
    """Record a ``timestamp`` in a result row's ``details`` (only when present).

    Mirrors :func:`mark_hidden_row`: a content row gets the flag as a sibling
    key; a row with no payload gains a metadata-only ``details`` (``type="item"``
    via the :class:`..models.data.BaseResult` validator). Call **after** the
    row's content ``details`` is built so the flag is not overwritten."""
    if timestamp:
        details = parsed.get("details")
        if not isinstance(details, dict):
            details = parsed["details"] = {"type": "item"}
        details["timestamp"] = timestamp
    return parsed


def mark_hidden_item(item: dict[str, Any], node: Node | None) -> dict[str, Any]:
    """Record ``visible=False`` on a ``details["items"]`` entry when ``node`` is
    hidden. Only-when-False, mirroring :func:`mark_hidden_row`."""
    if is_hidden(node):
        item["visible"] = False
    return item


def first_text(node: Node, css: str, sep: str = " ") -> str | None:
    """Stripped text of the first ``css`` match under ``node``, or ``None`` when
    there is no match or no text -- the common optional sub-field read that
    several card parsers each kept a private copy of."""
    return get_text(node.css_first(css), sep, strip=True) or None


def under_any(node: Node, ids: set[int], stop_id: int) -> bool:
    """True if any ancestor of ``node`` (up to ``stop_id``, exclusive) is in
    ``ids`` -- the "outermost emitted match wins" check the knowledge parsers
    use to skip markers nested inside an already-emitted sub-result."""
    p = node.parent
    while p is not None and p.mem_id != stop_id:
        if p.mem_id in ids:
            return True
        p = p.parent
    return False


def parse_alink(a: Node, sep: str = "", data_url_fallback: bool = False) -> dict[str, Any]:
    """Extract ``{"url", "text"}`` from an anchor node.

    Args:
        a: the anchor (``<a>``) node.
        sep: separator passed to ``get_text`` when joining multi-fragment link
            text. ``knowledge`` and the image carousel join with ``"|"``; most
            callers use ``""``.
        data_url_fallback: when the anchor has no usable ``href`` (lazy-loaded
            carousel thumbnails), fall back to the ``data-url`` attribute.

    A missing ``href`` (and ``data-url``, when ``data_url_fallback``) yields
    ``url=None`` rather than raising -- callers needing strict behavior must
    guard ``"href" in a.attrs`` before calling.
    """
    if data_url_fallback:
        url = a.attrs.get("href") or a.attrs.get("data-url")
    else:
        url = a.attrs.get("href")
    return {"url": url, "text": get_text(a, sep) or ""}


def parse_alink_list(alinks: Iterable[Node], sep: str = "") -> list[dict[str, Any]]:
    """Map ``parse_alink`` over real anchor tags that carry an ``href``."""
    items = []
    for a in alinks:
        if is_element(a) and "href" in a.attrs:
            items.append(parse_alink(a, sep))
    return items
