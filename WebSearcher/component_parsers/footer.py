"""Parsers for footer components.

Image-card grids, "discover more" carousels, and the omitted-results notice
that appear under the main results column.
"""

import bs4

from ..utils import find_all_divs, get_text


class Footer:
    @staticmethod
    def parse_image_cards(elem: bs4.element.Tag) -> list:
        subs = find_all_divs(elem, "div", {"class": "g"})
        return [Footer.parse_image_card(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    @staticmethod
    def parse_image_card(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
        parsed: dict = {"type": "img_cards", "sub_rank": sub_rank}
        parsed["title"] = get_text(sub, "div", {"aria-level": "3", "role": "heading"})
        images = sub.find_all("img")
        if images:
            items = [{"url": i["src"], "text": i["alt"]} for i in images]
            parsed["details"] = {"type": "hyperlinks", "items": items}
        return parsed

    @staticmethod
    def parse_discover_more(elem: bs4.element.Tag) -> list:
        carousel = elem.find("g-scrolling-carousel")
        text = "|".join(c.text for c in carousel.find_all("g-inner-card")) if carousel else ""
        return [{"type": "discover_more", "sub_rank": 0, "text": text}]

    @staticmethod
    def parse_omitted_notice(elem: bs4.element.Tag) -> list:
        return [{"type": "omitted_notice", "sub_rank": 0, "text": get_text(elem)}]
