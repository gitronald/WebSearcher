"""Parse an image carousel that appears at the top of the page above results.

Each item is a thumbnail link; the component itself has a title and points
at a parent listing.
"""

from selectolax.parser import Node

from .._slx import is_tag
from ..utils import get_link


def parse_top_image_carousel(cmpt: Node, sub_rank: int = 0) -> list:
    parsed: dict = {"type": "top_image_carousel", "sub_rank": sub_rank}

    title = cmpt.find_all("span", {"class": "Wkr6U"})
    if title:
        parsed["title"] = "|".join([t.text for t in title])
        parsed["url"] = get_link(cmpt)

    images = cmpt.find("div", {"role": "list"})
    if images:
        alinks: list = list(images.children)
    else:
        carousel = cmpt.find("g-scrolling-carousel")
        alinks = carousel.find_all("a") if carousel else []

    items = []
    for a in alinks:
        if not is_tag(a):
            continue
        if "href" in a.attrs or "data-url" in a.attrs:
            items.append(parse_alink(a))
    parsed["details"] = {"type": "hyperlinks", "items": items} if items else None

    return [parsed]


def parse_alink(a: Node) -> dict:
    url = a.attrs.get("href") or a.attrs.get("data-url", "")
    return {"url": url, "text": a.get_text("|")}
