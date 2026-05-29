"""Parse an "Images" component.

Three layouts: small thumbnails (with labels), medium image cards (with
title and URL), and a multimedia carousel (image / video previews without
text). Each subcomponent is tagged with the matching sub_type.
"""

from selectolax.parser import Node

from ..utils import get_div, get_link, get_text


def parse_images(cmpt: Node) -> list:
    parsed_list: list = []

    if cmpt.find("g-expandable-container"):
        # Small images: thumbnails with text labels
        subs = cmpt.find_all("a", {"class": "dgdd6c"})
        parsed_list.extend([parse_image_small(div, i) for i, div in enumerate(subs)])

    offset = len(parsed_list)
    if cmpt.find("g-scrolling-carousel"):
        # Medium images or video previews, no text labels
        subs = cmpt.find_all("div", {"class": "eA0Zlc"})
        parsed_list.extend([parse_image_multimedia(sub, i + offset) for i, sub in enumerate(subs)])
    else:
        # Medium images with titles and urls
        subs = cmpt.find_all("div", {"class": ["eA0Zlc", "vCUuC"]})
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
    title_div = get_div(sub, "a", {"class": "EZAeBe"})
    title = get_text(title_div) if title_div else get_text(sub, "span", {"class": "Yt787"})
    url = get_link(sub) if title_div else get_img_url(sub)

    if not title:
        title = get_img_alt(sub)
    if not url:
        url = get_link(sub, attrs={"class": ["EZAeBe", "ddkIM"]})

    return {
        "type": "images",
        "sub_type": "medium",
        "sub_rank": sub_rank,
        "title": title,
        "url": url,
        "text": None,
        "cite": get_text(sub, "div", {"class": "ptes9b"}),
    }


def parse_image_small(sub: Node, sub_rank: int = 0) -> dict:
    return {
        "type": "images",
        "sub_type": "small",
        "sub_rank": sub_rank,
        "title": get_text(sub, "div", {"class": "xlY4q"}),
        "url": None,
        "text": None,
    }


def get_img_url(sub: Node) -> str | None:
    # Try several extraction strategies; rejecting embedded data URLs
    def from_img_src(sub: Node) -> str:
        img = sub.find("img")
        return str(img.attrs["src"]) if img else ""

    def from_img_title(sub: Node) -> str:
        img = sub.find("img")
        return str(img.attrs["title"]) if img else ""

    def from_attrs(sub: Node) -> str:
        return str(sub.attrs["data-lpage"])

    for func in (from_img_src, from_attrs, from_img_title):
        try:
            url = func(sub)
            if url and not url.startswith("data:image"):
                return url
        except Exception:
            pass
    return None


def get_img_alt(sub: Node) -> str | None:
    try:
        img = sub.find("img")
        return f"alt-text: {img.attrs['alt']}" if img else None
    except Exception:
        return None
