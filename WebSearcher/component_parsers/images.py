"""Parse an "Images" component.

Three layouts: small thumbnails (with labels), medium image cards (with
title and URL), and a multimedia carousel (image / video previews without
text). Each subcomponent is tagged with the matching sub_type.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text


def parse_images(elem) -> list:
    node: Node = elem
    parsed_list: list = []

    if node.css_first("g-expandable-container") is not None:
        # Small images: thumbnails with text labels
        subs = node.css("a.dgdd6c")
        parsed_list.extend([parse_image_small(div, i) for i, div in enumerate(subs)])

    offset = len(parsed_list)
    if node.css_first("g-scrolling-carousel") is not None:
        # Medium images or video previews, no text labels
        subs = node.css("div.eA0Zlc")
        parsed_list.extend([parse_image_multimedia(sub, i + offset) for i, sub in enumerate(subs)])
    else:
        # Medium images with titles and urls -- class list = OR
        subs = node.css("div.eA0Zlc, div.vCUuC")
        parsed_list.extend([parse_image_medium(sub, i + offset) for i, sub in enumerate(subs)])

    return [p for p in parsed_list if any([p["title"], p["url"]])]


def parse_image_multimedia(sub: Node, sub_rank: int = 0) -> dict:
    return {
        "type": "images",
        "sub_type": "multimedia",
        "sub_rank": sub_rank,
        "title": get_img_alt(sub),
        "url": get_img_url(sub),
        "text": None,
    }


def parse_image_medium(sub: Node, sub_rank: int = 0) -> dict:
    title_a = sub.css_first("a.EZAeBe")
    title = (
        get_text(title_a, " ")
        if title_a is not None
        else get_text(sub.css_first("span.Yt787"), " ")
    )
    if title_a is not None:
        first_a = sub.css_first("a")
        url = first_a.attributes.get("href") if first_a is not None else None
    else:
        url = get_img_url(sub)

    if not title:
        title = get_img_alt(sub)
    if not url:
        fallback_a = sub.css_first("a.EZAeBe, a.ddkIM")
        url = fallback_a.attributes.get("href") if fallback_a is not None else None

    return {
        "type": "images",
        "sub_type": "medium",
        "sub_rank": sub_rank,
        "title": title,
        "url": url,
        "text": None,
        "cite": get_text(sub.css_first("div.ptes9b"), " "),
    }


def parse_image_small(sub: Node, sub_rank: int = 0) -> dict:
    return {
        "type": "images",
        "sub_type": "small",
        "sub_rank": sub_rank,
        "title": get_text(sub.css_first("div.xlY4q"), " "),
        "url": None,
        "text": None,
    }


def get_img_url(sub: Node) -> str | None:
    """Try several extraction strategies; reject embedded data: URLs."""
    img = sub.css_first("img")
    candidates: list[str | None] = []
    if img is not None:
        candidates.append(img.attributes.get("src"))
        candidates.append(img.attributes.get("title"))
    candidates.append(sub.attributes.get("data-lpage"))
    for url in candidates:
        if url and not url.startswith("data:image"):
            return str(url)
    return None


def get_img_alt(sub: Node) -> str | None:
    img = sub.css_first("img")
    alt = img.attributes.get("alt") if img is not None else None
    return f"alt-text: {alt}" if alt else None
