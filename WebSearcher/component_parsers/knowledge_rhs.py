"""Parse the Right-Hand-Side Knowledge Panel.

The wide-format entity panel that appears in the right-hand column. This
includes the main panel (title, description, image grid, submenu links) and
zero or more follow-on sections beneath it.
"""

from typing import Any

import bs4


def parse_knowledge_rhs(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list:
    parsed_list = parse_knowledge_rhs_main(cmpt)
    description = cmpt.find("h2", {"class": "Uo8X3b"})
    if description and description.parent:
        tag_subs = [s for s in description.parent.next_siblings if isinstance(s, bs4.element.Tag)]
        parsed_list.extend(parse_knowledge_rhs_sub(s, i) for i, s in enumerate(tag_subs))
    return parsed_list


def parse_knowledge_rhs_main(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list:
    parsed: dict[str, Any] = {
        "type": "knowledge",
        "sub_type": "panel_rhs",
        "sub_rank": sub_rank,
        "title": "",
        "text": "",
        "url": "",
        "details": {},
        "rhs_column": True,
    }

    # images
    h3 = cmpt.find("h3")
    if h3 and h3.text == "Images":
        sibling = h3.next_sibling
        if isinstance(sibling, bs4.element.Tag):
            imgs = sibling.find_all("a")
            parsed["details"]["img_urls"] = [img["href"] for img in imgs if "href" in img.attrs]

    # title, subtitle
    title = cmpt.find("h2", {"data-attrid": "title"})
    if title:
        parsed["title"] = title.text
    subtitle = cmpt.find("div", {"data-attrid": "subtitle"})
    if subtitle:
        parsed["details"]["subtitle"] = subtitle.text

    # description (heading-anchored)
    description = cmpt.find("h2", {"class": "Uo8X3b"})
    if description and description.parent:
        span = description.parent.find("span")
        if span:
            parsed["text"] = span.text
        a = description.parent.find("a")
        if a and "href" in a.attrs:
            parsed["url"] = a["href"]

    # description (kno-rdesc)
    description = cmpt.find("div", {"class": "kno-rdesc"})
    if description:
        span = description.find("span")
        parsed["text"] = span.text if span else parsed["text"]
        a = description.find("a")
        if a and "href" in a.attrs:
            parsed["url"] = a["href"]

    # submenu
    if description and description.parent:
        alinks = description.parent.find_all("a")
        prev = description.parent.previous_sibling
        if isinstance(prev, bs4.element.Tag):
            alinks += prev.find_all("a")
        if len(alinks) > 1:  # 1st match has main description
            urls = []
            for a in alinks[1:]:
                if "href" in a.attrs:
                    urls.append(parse_alink(a))
            parsed["details"]["urls"] = urls

    if parsed["details"]:
        parsed["details"]["type"] = "panel"
    else:
        parsed["details"] = None

    return [parsed]


def parse_knowledge_rhs_sub(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    parsed: dict = {
        "type": "knowledge",
        "sub_type": "panel_rhs",
        "sub_rank": sub_rank + 1,
        "title": "",
        "details": None,
        "rhs_column": True,
    }

    heading = sub.find("div", {"role": "heading"})
    if heading:
        parsed["title"] = heading.get_text(" ")

    alinks = sub.find_all("a")
    if alinks:
        items = []
        for a in alinks:
            if "href" in a.attrs:
                items.append(parse_alink(a))
        parsed["details"] = {"type": "hyperlinks", "items": items} if items else None

    return parsed


def parse_alink(a: bs4.element.Tag) -> dict:
    return {"url": a["href"], "text": a.text}
