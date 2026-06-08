"""Parsers for video components

Changelog
2024-05-08: added find_all for divs with class 'VibNM'
2024-05-08: added adjustment for new cite and timestamp
2025-04-27: added div subcomponent class and sub_type labels
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text, has_text
from ..models.data import ERR_NO_SUBCOMPONENTS, error_details
from ._common import mark_hidden_row

# (sub_type label, CSS selector); first selector that yields elements wins.
_SUBTYPE_SELECTORS: list[tuple[str, str]] = [
    ("unspecified-0", "g-inner-card"),
    ("unspecified-1", "div.VibNM"),
    ("unspecified-2", "div.mLmaBd"),
    ("unspecified-3", "div.RzdJxc"),
    ("vertical", "div.sHEJob"),
]


def parse_videos(elem) -> list:
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

    section_labels = {
        "Trailers & clips": "trailers-and-clips",
    }
    section_heading = node.css_first('div[role="heading"][aria-level="2"]')
    if section_heading is not None:
        label = section_labels.get(get_text(section_heading, " ", strip=True) or "")
        if label:
            sub_type = label

    if divs:
        return [parse_video(div, sub_type, i) for i, div in enumerate(divs)]
    return [{"type": "videos", "sub_rank": 0, "details": error_details(ERR_NO_SUBCOMPONENTS)}]


def parse_video(sub: Node, sub_type: str, sub_rank: int = 0) -> dict:
    parsed = {
        "type": "videos",
        "sub_type": sub_type,
        "sub_rank": sub_rank,
        "url": get_url(sub),
        "title": get_text(sub.css_first('div[role="heading"]'), " "),
        "text": get_text(sub.css_first("div.MjS0Lc"), " "),
    }

    details = list(sub.css("div.MjS0Lc"))
    if details:
        text_div = details[0] if len(details) >= 1 else None
        citetime_div = details[1] if len(details) >= 2 else None
        parsed["text"] = get_text(text_div) if text_div is not None else None

        if citetime_div is not None:
            citetime = citetime_div.css_first("div.zECGdd")
            if citetime is not None:
                items = list(citetime.iter(include_text=False))
                if len(items) == 2:
                    cite, _timestamp = items
                    parsed["cite"] = get_text(cite)
                elif items:
                    parsed["cite"] = get_text(items[0])
    elif sub.css_first("span.ocUPSd") is not None:
        parsed["cite"] = get_text(sub)
    elif sub.css_first("cite") is not None:
        parsed["cite"] = get_text(sub.css_first("cite"), " ")

    return mark_hidden_row(parsed, sub)


def get_url(sub: Node) -> str | None:
    """First non-hash href in the subcomponent."""
    for a in sub.css("a"):
        href = a.attributes.get("href")
        if href and not href.startswith("#"):
            return href
    return None
