"""Parse a "Videos" component.

A list or carousel of video tiles (frequently YouTube). Each row carries the
tile's url, heading, description text, source (``cite``), and, when the tile
ships Google's hidden ``evlb_*`` "About this result" card or key moments, a
``video`` details block via :func:`._video_card.video_details`.
``sub_type`` records which tile layout matched (see ``_SUBTYPE_SELECTORS``) or
the carousel's section heading (e.g. ``trailers-and-clips``).
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text, has_text, is_element
from ...models.data import ERR_NO_SUBCOMPONENTS, error_details
from ._common import mark_hidden_row, mark_timestamp_row
from ._video_card import video_details

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
    divs = sub.css("div.MjS0Lc")
    text_div = divs[0] if divs else None
    citetime_div = divs[1] if len(divs) >= 2 else None

    title, source_line = _read_heading(sub.css_first('div[role="heading"]'))
    parsed: dict[str, Any] = {
        "type": "videos",
        "sub_type": sub_type,
        "sub_rank": sub_rank,
        "url": get_url(sub),
        "title": title,
        "text": get_text(text_div, " "),
    }

    timestamp = None
    if citetime_div is not None:
        citetime = citetime_div.css_first("div.zECGdd")
        if citetime is not None:
            items = list(citetime.iter(include_text=False))
            if len(items) == 2:
                cite, timestamp = items
                parsed["cite"] = get_text(cite)
            elif items:
                parsed["cite"] = get_text(items[0])
    elif not divs:
        if sub.css_first("span.ocUPSd") is not None:
            parsed["cite"] = get_text(sub)
        elif (cite_el := sub.css_first("cite")) is not None:
            parsed["cite"] = get_text(cite_el, " ")
    # The line says more than a bare "YouTube" cite, and holds the only duration.
    if source_line and (parsed.get("cite") or "") in source_line:
        parsed["cite"] = source_line

    # Filled only now, since the deferred card holds headings and links of its
    # own. Content details first, so the timestamp/visible flags ride as siblings.
    details = video_details(sub)
    if details:
        parsed["details"] = details
    mark_timestamp_row(parsed, get_text(timestamp) if timestamp is not None else None)
    return mark_hidden_row(parsed, sub)


def _read_heading(heading: Node | None) -> tuple[str | None, str | None]:
    """A heading's title and, when it has one, its source line.

    A tile's heading holds the title, then a line with the source, channel, duration,
    and date. By position, since the classes are generated. Any other shape is read
    whole, so a layout change gives a long title rather than a wrong or empty one.
    """
    if heading is None:
        return None, None
    parts = [part for part in heading.iter(include_text=False) if is_element(part)]
    if len(parts) == 2:
        title = get_text(parts[0], " ")
        if title:
            return title, get_text(parts[1], " ", strip=True)
    return get_text(heading, " "), None


def get_url(sub: Node) -> str | None:
    """First non-hash href in the subcomponent."""
    for a in sub.css("a"):
        href = a.attrs.get("href")
        if href and not href.startswith("#"):
            return href
    return None
