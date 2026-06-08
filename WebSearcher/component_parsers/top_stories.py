"""Parse a "Top Stories" component.

These components contain links to news articles and often feature an image.
Sometimes the subcomponents are stacked vertically, and sometimes they are
stacked horizontally and feature a larger image, resembling the video
component.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text, has_text
from ..models.data import ERR_NO_SUBCOMPONENTS, error_details
from ._common import mark_hidden_row


def parse_top_stories(elem, ctype: str = "top_stories") -> list:
    node: Node = elem
    divs: list[Node] = []
    divs.extend(d for d in node.css("g-inner-card") if has_text(d))  # Top Stories
    # find_children equivalent: direct element children of div.qmv19b (no empty filter)
    container = node.css_first("div.qmv19b")
    if container is not None:
        divs.extend(container.iter(include_text=False))
    divs.extend(d for d in node.css("div.IJl0Z") if has_text(d))  # Top Stories
    divs.extend(d for d in node.css("div.JJZKK") if has_text(d))  # Perspectives

    if not divs:
        # Modern Perspectives: every carousel item is role=listitem (covers both
        # standard cards and embedded tweets, including AI-themed sub-carousels).
        divs.extend(node.css('[role="listitem"]'))

    if not divs:
        # Older Top Stories vertical layout
        link_divs = [d for d in node.css("a.WlydOe") if has_text(d)]
        divs.extend([div.parent for div in link_divs if div.parent is not None])

    divs = [d for d in divs if d is not None]

    if divs:
        return [parse_top_story(div, ctype, i) for i, div in enumerate(divs)]
    return [{"type": ctype, "sub_rank": 0, "details": error_details(ERR_NO_SUBCOMPONENTS)}]


def parse_top_story(sub: Node, ctype: str, sub_rank: int = 0) -> dict:
    title = None
    for sel in ("div.n0jPhd", "div.eAaXgc", "div.xcQxib"):
        t = get_text(sub.css_first(sel), " ")
        if t:
            title = t
            break
    a = sub.css_first("a")
    url = a.attributes.get("href") if a is not None else None
    parsed = {
        "type": ctype,
        "sub_rank": sub_rank,
        "title": title,
        "url": url,
        "text": get_text(sub.css_first("div.GI74Re"), " "),
        "cite": get_cite(sub),
    }
    return mark_hidden_row(parsed, sub)


def get_cite(sub: Node) -> str | None:
    div_cite = sub.css_first("div.Dx69l")  # Perspectives
    if div_cite is not None:
        return get_text(div_cite, " ")

    tweet_cite = sub.css_first("div.Du2Vwd")  # Perspectives - embedded tweet
    if tweet_cite is not None:
        return get_text(tweet_cite, " ")

    img_cite = sub.css_first("g-img.sL0zmc")  # Top Stories - image cite
    if img_cite is not None:
        img = img_cite.css_first("img")
        alt = img.attributes.get("alt") if img is not None else None
        return str(alt) if alt else None

    if sub.css_first("g-img.QyR1Ze") is not None:
        return get_text(sub.css_first("span"), " ")
    return get_text(sub.css_first("cite"), " ")


def get_top_story_details(sub: Node) -> dict:
    return {
        "img_url": get_img_url(sub),
        "orient": "v" if sub.css_first("span.uaCsqe") is not None else "h",
        "live_stamp": sub.css_first("span.EugGe") is not None,
    }


def get_img_url(node: Node) -> str | None:
    img = node.css_first("img")
    if img is not None and "data-src" in img.attributes:
        return str(img.attributes["data-src"])
    return None
