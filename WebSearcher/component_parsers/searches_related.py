"""Parse a "Searches related" component.

A one- or two-column list of related search-query suggestions. Variants
include the classic suggestion list, curated lists (e.g. song names),
accordion-style sections, and link rows under "brs_col".
"""

import bs4

from ..utils import Selector, find_all_divs, get_text, get_text_by_selectors


def parse_searches_related(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list:
    parsed: dict = {
        "type": "searches_related",
        "sub_rank": sub_rank,
        "title": None,
        "url": None,
    }

    # First non-empty header becomes the sub_type (e.g. "Additional searches" -> additional_searches)
    header_selectors = [
        Selector("h2", {"role": "heading"}),
        Selector("div", {"aria-level": "2", "role": "heading"}),
    ]
    header = get_text_by_selectors(cmpt, header_selectors)
    parsed["sub_type"] = header.lower().replace(" ", "_") if header else None

    output_list: list[str] = []

    # Classic search query suggestions
    subs = find_all_divs(cmpt, "a", {"class": "k8XOCe"})
    output_list.extend(filter(None, (sub.text.strip() for sub in subs)))

    # Curated list (e.g. song names)
    subs = find_all_divs(cmpt, "div", {"class": "EASEnb"})
    output_list.extend(filter(None, (sub.text.strip() for sub in subs)))

    # Other list types
    subs = find_all_divs(cmpt, "div", {"role": "listitem"})
    output_list.extend(filter(None, (sub.text.strip() for sub in subs)))

    # Accordion list
    if cmpt.find("explore-desktop-accordion"):
        subs = find_all_divs(cmpt, "div", {"class": "JXa4nd"})
        text_list = [
            get_text(sub, "div", {"class": "Cx1ZMc"})
            for sub in subs
            if isinstance(sub, bs4.element.Tag)
        ]
        output_list.extend(filter(None, text_list))

    if cmpt.find("div", {"class": "brs_col"}):
        subs = find_all_divs(cmpt, "a")
        output_list.extend(filter(None, (sub.text.strip() for sub in subs)))

    parsed["text"] = "<|>".join(output_list)
    parsed["details"] = {"type": "text", "items": output_list} if output_list else None
    return [parsed]
