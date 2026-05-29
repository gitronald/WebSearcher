"""Parse a "View more news" component.

Highly similar to the vertically stacked Top Stories and Latest news layouts,
but distinguished by a news icon in the top left.
"""

from selectolax.parser import Node

from .._slx import is_tag


def parse_view_more_news(cmpt: Node) -> list:
    container = cmpt.find("div", {"class": "qmv19b"})
    if container:
        subs: list = list(container.children)
    else:
        carousel = cmpt.find("g-scrolling-carousel")
        subs = carousel.find_all("g-inner-card") if carousel else []
    return [parse_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs) if is_tag(sub)]


def parse_sub(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "view_more_news", "sub_rank": sub_rank}
    title_div = sub.find("div", {"class": "jBgGLd"})
    a = sub.find("a")
    parsed["title"] = title_div.text if title_div else None
    parsed["url"] = a.attrs["href"] if a else None

    cite_span = sub.find("span", {"class": "wqg8ad"})
    cite_el = sub.find("cite")
    if cite_span:
        parsed["cite"] = cite_span.text
    elif cite_el:
        parsed["cite"] = cite_el.text

    timestamp_span = sub.find("span", {"class": "FGlSad"}) or sub.find("span", {"class": "f"})
    if timestamp_span:
        parsed["timestamp"] = timestamp_span.text

    parsed["img_url"] = get_img_url(sub)
    return parsed


def get_img_url(soup: Node) -> str | None:
    img = soup.find("img")
    if img and "data-src" in img.attrs:
        return str(img.attrs["data-src"])
    return None
