"""Shared helpers for component parsers.

Hosts the link-extraction helpers that several parsers each kept a near-identical
private copy of before plan 028. One parameterized ``parse_alink`` covers the
small, documented behavior differences (text separator, ``data-url`` fallback)
via explicit arguments.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text


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
