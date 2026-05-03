from .. import utils

_HEADER_SELECTORS = [
    ("h2", {"role": "heading"}),
    ("div", {"aria-level": "2", "role": "heading"}),
]


def parse_searches_related(cmpt, sub_rank=0) -> list:
    """Parse a one or two column list of related search queries"""

    parsed = {
        "type": "searches_related",
        "sub_rank": sub_rank,
        "title": None,
        "url": None,
    }

    # Set first non-empty header as sub_type (e.g. "Additional searches" -> additional_searches)
    header = utils.get_text_by_selectors(cmpt, _HEADER_SELECTORS)
    parsed["sub_type"] = header.lower().replace(" ", "_") if header else None

    output_list = []

    # Classic search query suggestions
    subs = utils.find_all_divs(cmpt, "a", {"class": "k8XOCe"})
    text_list = [sub.text.strip() for sub in subs]
    output_list.extend(filter(None, text_list))

    # Curated list (e.g. song names)
    subs = utils.find_all_divs(cmpt, "div", {"class": "EASEnb"})
    text_list = [sub.text.strip() for sub in subs]
    output_list.extend(filter(None, text_list))

    # Other list types
    subs = utils.find_all_divs(cmpt, "div", {"role": "listitem"})
    text_list = [sub.text.strip() for sub in subs]
    output_list.extend(filter(None, text_list))

    # Accordion list
    if cmpt.find("explore-desktop-accordion"):
        from bs4.element import Tag

        subs = utils.find_all_divs(cmpt, "div", {"class": "JXa4nd"})
        text_list = [
            utils.get_text(sub, "div", {"class": "Cx1ZMc"}) for sub in subs if isinstance(sub, Tag)
        ]
        output_list.extend(filter(None, text_list))

    if cmpt.find("div", {"class": "brs_col"}):
        subs = utils.find_all_divs(cmpt, "a")
        link_text = [sub.text.strip() for sub in subs]
        output_list.extend(filter(None, link_text))

    parsed["text"] = "<|>".join(output_list)
    parsed["details"] = {"type": "text", "items": output_list} if output_list else None
    return [parsed]
