"""Parse a "Searches related" component.

A one- or two-column list of related search-query suggestions. Variants
include the classic suggestion list, curated lists (e.g. song names),
accordion-style sections, and link rows under "brs_col".
"""

from selectolax.parser import Node

from .._slx import get_text, has_text
from ..utils import slugify


def parse_searches_related(cmpt, sub_rank: int = 0) -> list:
    node: Node = cmpt
    parsed: dict = {
        "type": "searches_related",
        "sub_rank": sub_rank,
        "title": None,
        "url": None,
    }

    # First non-empty header becomes the sub_type (e.g. "Additional searches" -> additional_searches)
    header = None
    for sel in ('h2[role="heading"]', 'div[aria-level="2"][role="heading"]', "span.mgAbYb"):
        found = node.css_first(sel)
        text = get_text(found, " ") if found is not None else None
        if text:
            header = text
            break
    parsed["sub_type"] = slugify(header.lower()) if header else None

    output_list: list[str] = []

    def _push(items):
        for item in items:
            text = (get_text(item) or "").strip()
            if text:
                output_list.append(text)

    # Classic search query suggestions
    _push(s for s in node.css("a.k8XOCe") if has_text(s))

    # Curated list (e.g. song names)
    _push(s for s in node.css("div.EASEnb") if has_text(s))

    # Other list types
    _push(s for s in node.css('div[role="listitem"]') if has_text(s))

    # Current Google layout: anchor links
    _push(s for s in node.css("a.ngTNl") if has_text(s))

    # Accordion list
    if node.css_first("explore-desktop-accordion") is not None:
        for s in node.css("div.JXa4nd"):
            if has_text(s):
                text = get_text(s.css_first("div.Cx1ZMc"), " ")
                if text:
                    output_list.append(text)

    if node.css_first("div.brs_col") is not None:
        _push(s for s in node.css("a") if has_text(s))

    parsed["text"] = "<|>".join(output_list)
    if output_list:
        details: dict = {"type": "text", "items": output_list}
        if header:
            details["heading"] = header  # preserve the raw header text (the sub_type slug is lossy)
        parsed["details"] = details
    else:
        parsed["details"] = None
    return [parsed]
