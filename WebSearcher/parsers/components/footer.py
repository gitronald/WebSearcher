"""Parsers for footer components.

Image-card grids, "discover more" carousels, and the omitted-results notice
that appear under the main results column.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text, has_text, subtree_css
from ._common import mark_hidden_item, mark_hidden_row


def parse_img_cards(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    subs = [d for d in subtree_css(node, "div.g") if has_text(d)]
    return [parse_img_card(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_img_card(sub: Node, sub_rank: int = 0) -> dict[str, Any]:
    parsed: dict[str, Any] = {"type": "img_cards", "sub_rank": sub_rank}
    parsed["title"] = get_text(sub.css_first('div[aria-level="3"][role="heading"]'), " ")
    items = [
        mark_hidden_item({"url": i.attrs["src"], "text": i.attrs["alt"]}, i)
        for i in sub.css("img")
        if "src" in i.attrs and "alt" in i.attrs
    ]
    # Only images carrying both src and alt are recorded; emit no details
    # rather than a hollow ``{"type": "hyperlinks", "items": []}``.
    if items:
        parsed["details"] = {"type": "hyperlinks", "items": items}
    return mark_hidden_row(parsed, sub)


def parse_discover_more(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    carousel = node.css_first("g-scrolling-carousel")
    text = (
        "|".join((get_text(c) or "") for c in carousel.css("g-inner-card"))
        if carousel is not None
        else ""
    )
    return [{"type": "discover_more", "sub_rank": 0, "text": text}]


def parse_omitted_notice(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    return [{"type": "omitted_notice", "sub_rank": 0, "text": get_text(node, " ")}]
