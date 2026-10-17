"""Parse a "Videos" component.

A list or carousel of video tiles (frequently YouTube). Each row carries the
tile's url, heading, description text, source (``cite``), and, when the tile
ships Google's hidden ``evlb_*`` "About this result" card, a ``video`` details
block (channel, upload date, duration) via :func:`._video_card.parse_evlb_card`.
``sub_type`` records which tile layout matched (see ``_SUBTYPE_SELECTORS``) or
the carousel's section heading (e.g. ``trailers-and-clips``).
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text, has_text
from ...models.data import ERR_NO_SUBCOMPONENTS, error_details
from ._common import mark_hidden_row, mark_timestamp_row
from ._video_card import parse_evlb_card

# (sub_type label, CSS selector); first selector that yields elements wins.
_SUBTYPE_SELECTORS: list[tuple[str, str]] = [
    ("unspecified-0", "g-inner-card"),
    ("unspecified-1", "div.VibNM"),
    ("unspecified-2", "div.mLmaBd"),
    ("unspecified-3", "div.RzdJxc"),
    ("vertical", "div.sHEJob"),
]

_SECTION_LABELS: dict[str, str] = {
    "Trailers & clips": "trailers-and-clips",
}


def parse_videos(elem: Node) -> list[dict[str, Any]]:
    """Parse a videos component (links to videos, frequently YouTube)."""
    node: Node = elem

    divs: list[Node] = []
    sub_type = "unspecified-0"
    for label, sel in _SUBTYPE_SELECTORS:
        found = [d for d in node.css(sel) if has_text(d)]
        if found:
            divs = found
            sub_type = label
            break

    section_heading = node.css_first('div[role="heading"][aria-level="2"]')
    if section_heading is not None:
        label = _SECTION_LABELS.get(get_text(section_heading, " ", strip=True) or "")
        if label:
            sub_type = label

    if divs:
        return [parse_video(div, sub_type, i) for i, div in enumerate(divs)]
    return [{"type": "videos", "sub_rank": 0, "details": error_details(ERR_NO_SUBCOMPONENTS)}]


def parse_video(sub: Node, sub_type: str, sub_rank: int = 0) -> dict[str, Any]:
    # The first div.MjS0Lc holds the description, the second the cite/timestamp.
    details = sub.css("div.MjS0Lc")
    text_div = details[0] if details else None
    citetime_div = details[1] if len(details) >= 2 else None

    parsed: dict[str, Any] = {
        "type": "videos",
        "sub_type": sub_type,
        "sub_rank": sub_rank,
        "url": get_url(sub),
        "title": get_text(sub.css_first('div[role="heading"]'), " "),
        "text": get_text(text_div, " "),
    }

    # Content details first, so the timestamp/visible flags ride as siblings.
    fields = parse_evlb_card(sub)
    if fields:
        parsed["details"] = {"type": "video", **fields}

    if citetime_div is not None:
        citetime = citetime_div.css_first("div.zECGdd")
        if citetime is not None:
            items = list(citetime.iter(include_text=False))
            if len(items) == 2:
                cite, timestamp = items
                parsed["cite"] = get_text(cite)
                mark_timestamp_row(parsed, get_text(timestamp))
            elif items:
                parsed["cite"] = get_text(items[0])
    elif not details:
        if sub.css_first("span.ocUPSd") is not None:
            parsed["cite"] = get_text(sub)
        elif (cite_el := sub.css_first("cite")) is not None:
            parsed["cite"] = get_text(cite_el, " ")

    return mark_hidden_row(parsed, sub)


def get_url(sub: Node) -> str | None:
    """First non-hash href in the subcomponent."""
    for a in sub.css("a"):
        href = a.attrs.get("href")
        if href and not href.startswith("#"):
            return href
    return None
