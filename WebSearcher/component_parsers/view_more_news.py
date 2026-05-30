"""Parse a "View more news" component.

Highly similar to the vertically stacked Top Stories and Latest news layouts,
but distinguished by a news icon in the top left.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text


def parse_view_more_news(elem) -> list:
    node: Node = elem
    container = node.css_first("div.qmv19b")
    if container is not None:
        # Bs4 .children yielded both Tags and NavigableStrings; the original
        # filtered with is_tag, so element-only iteration matches.
        subs = list(container.iter(include_text=False))
    else:
        carousel = node.css_first("g-scrolling-carousel")
        subs = list(carousel.css("g-inner-card")) if carousel is not None else []
    return [parse_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_sub(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "view_more_news", "sub_rank": sub_rank}
    title_div = sub.css_first("div.jBgGLd")
    a = sub.css_first("a")
    parsed["title"] = get_text(title_div) if title_div is not None else None
    parsed["url"] = a.attributes["href"] if a is not None else None

    cite_span = sub.css_first("span.wqg8ad")
    cite_el = sub.css_first("cite")
    if cite_span is not None:
        parsed["cite"] = get_text(cite_span)
    elif cite_el is not None:
        parsed["cite"] = get_text(cite_el)

    timestamp_span = sub.css_first("span.FGlSad") or sub.css_first("span.f")
    if timestamp_span is not None:
        parsed["timestamp"] = get_text(timestamp_span)

    parsed["img_url"] = get_img_url(sub)
    return parsed


def get_img_url(node: Node) -> str | None:
    img = node.css_first("img")
    if img is not None and "data-src" in img.attributes:
        return str(img.attributes["data-src"])
    return None
