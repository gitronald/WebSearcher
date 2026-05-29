"""Parsers for footer components.

Image-card grids, "discover more" carousels, and the omitted-results notice
that appear under the main results column.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text, has_text


class Footer:
    @staticmethod
    def parse_image_cards(elem) -> list:
        node: Node = elem
        subs = [d for d in node.css("div.g") if d.mem_id != node.mem_id and has_text(d)]
        return [Footer.parse_image_card(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    @staticmethod
    def parse_image_card(sub: Node, sub_rank: int = 0) -> dict:
        parsed: dict = {"type": "img_cards", "sub_rank": sub_rank}
        parsed["title"] = get_text(
            sub.css_first('div[aria-level="3"][role="heading"]'), " "
        )
        images = sub.css("img")
        if images:
            items = [
                {"url": i.attributes["src"], "text": i.attributes["alt"]}
                for i in images
                if "src" in i.attributes and "alt" in i.attributes
            ]
            parsed["details"] = {"type": "hyperlinks", "items": items}
        return parsed

    @staticmethod
    def parse_discover_more(elem) -> list:
        node: Node = elem
        carousel = node.css_first("g-scrolling-carousel")
        text = (
            "|".join((get_text(c) or "") for c in carousel.css("g-inner-card"))
            if carousel is not None
            else ""
        )
        return [{"type": "discover_more", "sub_rank": 0, "text": text}]

    @staticmethod
    def parse_omitted_notice(elem) -> list:
        node: Node = elem
        return [{"type": "omitted_notice", "sub_rank": 0, "text": get_text(node)}]
