"""Parsers for footer components.

Image-card grids, "discover more" carousels, and the omitted-results notice
that appear under the main results column.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text, has_text, is_hidden


def parse_img_cards(elem) -> list:
    node: Node = elem
    subs = [d for d in node.css("div.g") if d.mem_id != node.mem_id and has_text(d)]
    return [parse_img_card(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_img_card(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "img_cards", "sub_rank": sub_rank, "visible": not is_hidden(sub)}
    parsed["title"] = get_text(sub.css_first('div[aria-level="3"][role="heading"]'), " ")
    images = sub.css("img")
    if images:
        items = [
            {"url": i.attributes["src"], "text": i.attributes["alt"], "visible": not is_hidden(i)}
            for i in images
            if "src" in i.attributes and "alt" in i.attributes
        ]
        parsed["details"] = {"type": "hyperlinks", "items": items}
    return parsed


def parse_discover_more(elem) -> list:
    node: Node = elem
    carousel = node.css_first("g-scrolling-carousel")
    text = (
        "|".join((get_text(c) or "") for c in carousel.css("g-inner-card"))
        if carousel is not None
        else ""
    )
    return [{"type": "discover_more", "sub_rank": 0, "text": text}]


def parse_omitted_notice(elem) -> list:
    node: Node = elem
    return [{"type": "omitted_notice", "sub_rank": 0, "text": get_text(node, " ")}]
