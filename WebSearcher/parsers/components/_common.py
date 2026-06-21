"""Shared helpers for component parsers.

Hosts the link-extraction helpers that several parsers each kept a near-identical
private copy of before plan 028. One parameterized ``parse_alink`` covers the
small, documented behavior differences (text separator, ``data-url`` fallback)
via explicit arguments.
"""

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text, is_hidden


def mark_hidden_row(parsed: dict, node: Node | None) -> dict:
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


def mark_timestamp_row(parsed: dict, timestamp: str | None) -> dict:
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


def mark_hidden_item(item: dict, node: Node | None) -> dict:
    """Record ``visible=False`` on a ``details["items"]`` entry when ``node`` is
    hidden. Only-when-False, mirroring :func:`mark_hidden_row`."""
    if is_hidden(node):
        item["visible"] = False
    return item


def parse_alink(a: Node, sep: str = "", data_url_fallback: bool = False) -> dict:
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
    guard ``"href" in a.attributes`` before calling.
    """
    if data_url_fallback:
        url = a.attributes.get("href") or a.attributes.get("data-url")
    else:
        url = a.attributes.get("href")
    return {"url": url, "text": get_text(a, sep) or ""}


def parse_alink_list(alinks, sep: str = "") -> list:
    """Map ``parse_alink`` over real anchor tags that carry an ``href``."""
    items = []
    for a in alinks:
        if a.tag and not a.tag.startswith("-") and "href" in a.attributes:
            items.append(parse_alink(a, sep))
    return items
