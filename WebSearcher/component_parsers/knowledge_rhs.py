"""Parse the Right-Hand-Side Knowledge Panel.

The wide-format entity panel that appears in the right-hand column. This
includes the main panel (title, description, image grid, submenu links) and
zero or more follow-on sections beneath it.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text, next_sibling, next_siblings, previous_sibling
from ._common import parse_alink


def parse_knowledge_rhs(elem, sub_rank: int = 0) -> list:
    node: Node = elem
    parsed_list = parse_knowledge_rhs_main(node)
    description = node.css_first("h2.Uo8X3b")
    if description is not None and description.parent is not None:
        tag_subs = [
            s for s in next_siblings(description.parent) if s.tag and not s.tag.startswith("-")
        ]
        for i, s in enumerate(tag_subs):
            sub = parse_knowledge_rhs_sub(s, i)
            # Skip hollow follow-on sections (no heading and no links).
            if sub["title"] or sub["details"]:
                parsed_list.append(sub)
    return parsed_list


def parse_knowledge_rhs_main(elem, sub_rank: int = 0) -> list:
    node: Node = elem
    parsed: dict[str, Any] = {
        "type": "knowledge",
        "sub_type": "panel_rhs",
        "sub_rank": sub_rank,
        "title": None,
        "text": None,
        "url": None,
        "details": {},
        "rhs_column": True,
    }

    # images
    h3 = node.css_first("h3")
    if h3 is not None and (get_text(h3) or "") == "Images":
        sibling = next_sibling(h3)
        if sibling is not None and sibling.tag and not sibling.tag.startswith("-"):
            imgs = sibling.css("a")
            parsed["details"]["img_urls"] = [
                img.attributes["href"] for img in imgs if "href" in img.attributes
            ]

    # title, subtitle (data-attrid carries the title on any tag, not just h2)
    title = node.css_first('h2[data-attrid="title"]') or node.css_first('[data-attrid="title"]')
    if title is not None:
        parsed["title"] = get_text(title, " ", strip=True) or None
    subtitle = node.css_first('div[data-attrid="subtitle"]')
    if subtitle is not None:
        parsed["details"]["subtitle"] = get_text(subtitle)

    # description (heading-anchored)
    description = node.css_first("h2.Uo8X3b")
    if description is not None and description.parent is not None:
        span = description.parent.css_first("span")
        if span is not None:
            parsed["text"] = get_text(span)
        a = description.parent.css_first("a")
        if a is not None and "href" in a.attributes:
            parsed["url"] = a.attributes["href"]

    # description (kno-rdesc)
    description = node.css_first("div.kno-rdesc")
    if description is not None:
        span = description.css_first("span")
        parsed["text"] = get_text(span) if span is not None else parsed["text"]
        a = description.css_first("a")
        if a is not None and "href" in a.attributes:
            parsed["url"] = a.attributes["href"]

    # submenu
    if description is not None and description.parent is not None:
        alinks = list(description.parent.css("a"))
        prev = previous_sibling(description.parent)
        if prev is not None and prev.tag and not prev.tag.startswith("-"):
            alinks += list(prev.css("a"))
        if len(alinks) > 1:  # 1st match has main description
            urls = []
            for a in alinks[1:]:
                if "href" in a.attributes:
                    urls.append(parse_alink(a))
            parsed["details"]["urls"] = urls

    # description fallback (entity panels whose description sits on a
    # data-attrid rather than Uo8X3b / kno-rdesc)
    if not parsed["text"]:
        desc = node.css_first("[data-attrid=description]")
        if desc is not None:
            parsed["text"] = get_text(desc, " ", strip=True) or None

    # "Things to know" RHS panels carry topic sections on lab/title/* attrs
    # rather than a single description -- surface the topics instead of an
    # empty placeholder.
    topics = [
        attr.split("/")[-1]
        for d in node.css("[data-attrid]")
        if (attr := str(d.attributes.get("data-attrid") or "")).startswith("lab/title/")
    ]
    if topics:
        if not parsed["title"]:
            parsed["title"] = "Things to know"
        parsed["details"]["items"] = topics

    if parsed["details"]:
        parsed["details"]["type"] = "panel"
    else:
        parsed["details"] = None

    # Drop genuinely hollow placeholder rows (nothing extracted at all).
    if (
        not parsed["title"]
        and not parsed["text"]
        and not parsed["url"]
        and parsed["details"] is None
    ):
        return []

    return [parsed]


def parse_knowledge_rhs_sub(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {
        "type": "knowledge",
        "sub_type": "panel_rhs",
        "sub_rank": sub_rank + 1,
        "title": None,
        "details": None,
        "rhs_column": True,
    }

    heading = sub.css_first('div[role="heading"]')
    if heading is not None:
        parsed["title"] = get_text(heading, " ") or None

    alinks = list(sub.css("a"))
    if alinks:
        items = []
        for a in alinks:
            if "href" in a.attributes:
                items.append(parse_alink(a))
        parsed["details"] = {"type": "hyperlinks", "items": items} if items else None

    return parsed
