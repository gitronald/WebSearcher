"""Parse an image carousel that appears at the top of the page above results.

Each item is a thumbnail link; the component itself has a title and points
at a parent listing.
"""

from selectolax.parser import Node

from .._slx import get_text


def parse_top_image_carousel(cmpt, sub_rank: int = 0) -> list:
    node: Node = cmpt
    parsed: dict = {"type": "top_image_carousel", "sub_rank": sub_rank}

    titles = node.css("span.Wkr6U")
    if titles:
        parsed["title"] = "|".join((get_text(t) or "") for t in titles)
        a = node.css_first("a")
        parsed["url"] = a.attributes.get("href") if a is not None else None

    images = node.css_first('div[role="list"]')
    if images is not None:
        # bs4 .children with is_tag filter == element-only iteration here.
        alinks = list(images.iter(include_text=False))
    else:
        carousel = node.css_first("g-scrolling-carousel")
        alinks = list(carousel.css("a")) if carousel is not None else []

    items = []
    for a in alinks:
        if "href" in a.attributes or "data-url" in a.attributes:
            items.append(parse_alink(a))
    parsed["details"] = {"type": "hyperlinks", "items": items} if items else None

    return [parsed]


def parse_alink(a: Node) -> dict:
    url = a.attributes.get("href") or a.attributes.get("data-url", "")
    return {"url": url, "text": get_text(a, "|")}
