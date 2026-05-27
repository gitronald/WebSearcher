"""Parse a "General" results component.

The ubiquitous blue-title / green-citation / black-summary results, sometimes
grouped into multi-result components with related themes. Subtypes include
submenus (rating, list, table, mini), scholarly results, products, and videos.
"""

import re

import bs4

from .._slx import is_tag
from ..utils import get_link, get_text


def parse_general_results(cmpt: bs4.element.Tag) -> list:
    subs = find_subcomponents(cmpt)
    return [parse_general_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def find_subcomponents(cmpt: bs4.element.Tag) -> list:
    # Standard format
    subs = cmpt.find_all("div", {"class": "g"})
    if subs:
        parent_g = subs[0]  # first .g in document order (== cmpt.find("div", {"class": "g"}))
        if parent_g.find("div", {"class": "g"}):
            return [parent_g]  # Nested .g dedup
        return subs

    # Sub-results format (2023+)
    additional = cmpt.find_all("div", {"class": "d4rhi"})
    if additional:
        first = cmpt.find("div")
        return [first] + list(additional) if first else list(additional)

    # Video results
    subs = cmpt.find_all("div", {"class": "PmEWq"})
    if subs:
        return list(subs)

    # Fallback: treat entire component as single result
    return [cmpt]


def parse_general_result(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    if is_general_video(sub):
        return parse_general_video(sub, sub_rank=sub_rank)

    title_div = sub.find("div", {"class": "rc"}) or sub.find("div", {"class": "yuRUbf"})
    body_div = sub.find("span", {"class": "st"}) or sub.find("div", {"class": "VwiC3b"})

    parsed: dict = {
        "type": "general",
        "sub_rank": sub_rank,
        "title": get_text(title_div, "h3") if title_div else None,
        "url": get_link(title_div) if title_div else None,
        "text": get_text(body_div) if body_div else None,
        "cite": get_text(sub, "cite"),
    }

    if parsed["title"] is None and parsed["url"] is None:
        parsed["error"] = "no title or url"

    return parse_subtype_details(sub, parsed)


def parse_alink(a: bs4.element.Tag) -> dict:
    return {"url": a.attrs["href"], "text": a.text}


def parse_alink_list(alinks) -> list:
    items = []
    for a in alinks:
        if is_tag(a) and "href" in a.attrs:
            items.append(parse_alink(a))
    return items


def parse_subtype_details(sub: bs4.element.Tag, parsed: dict) -> dict:
    details: dict = {}

    # If top menu with children, ignore URLs and get correct title URL
    top_menu = sub.find("div", {"class": "yWc32e"})
    if top_menu:
        has_children = list(top_menu.children)
        if has_children:
            for child in top_menu.children:
                child.decompose()
            h3 = sub.find("h3")
            if h3:
                a = h3.find("a")
                if a:
                    parsed["url"] = a["href"]

    if "d4rhi" in sub.attrs.get("class", []):
        parsed["sub_type"] = "subresult"

    elif sub.find("div", {"class": "d86Vh"}):
        # Image thumbnail strip (e.g. Pinterest board, Etsy market, shop pages):
        # a horizontal row of g-img previews that all link back to the result.
        # The thumbnails are JS-driven data: placeholders with no per-image url
        # or alt text, so only the layout is flagged -- there is nothing that
        # fits an existing details schema to capture.
        parsed["sub_type"] = "image_strip"

    elif sub.find("g-review-stars"):
        # Submenu - rating
        parsed["sub_type"] = "submenu_rating"
        stars = sub.find("g-review-stars")
        sibling = stars.next_sibling if stars else None
        if sibling:
            text = str(sibling).strip()
            if len(text):
                ratings = parse_ratings(text.split("-"))
                details.update(ratings)
                details["type"] = "review"

    elif sub.find("div", {"class": ["P1usbc", "IThcWe"]}):
        # Submenu - list format
        parsed["sub_type"] = "submenu"
        submenu_div = sub.find("div", {"class": ["P1usbc", "IThcWe"]})
        if submenu_div:
            alinks = submenu_div.find_all("a")
            details["type"] = "hyperlinks"
            details["items"] = parse_alink_list(alinks)

    elif sub.find("table"):
        # Submenu - table format
        parsed["sub_type"] = "submenu"
        table = sub.find("table")
        alinks = table.find_all("a") if table else []
        details["type"] = "hyperlinks"
        details["items"] = parse_alink_list(alinks)

    elif sub.find("div", {"class": ["osl", "jYOxx"]}):
        # Mini submenu
        parsed["sub_type"] = "submenu_mini"
        submenu = sub.find("div", {"class": ["osl", "jYOxx"]})
        alinks = submenu.find_all("a") if submenu else []
        details["type"] = "hyperlinks"
        details["items"] = parse_alink_list(alinks)

    elif sub.find("div", {"class": re.compile("fG8Fp")}):
        scholar_div = sub.find("div", {"class": re.compile("fG8Fp")})
        alinks = scholar_div.find_all("a") if scholar_div else []
        if len(alinks) and "Cited by" in alinks[0].text:
            # Scholar results
            parsed["sub_type"] = "submenu_scholarly"
            details["type"] = "hyperlinks"
            details["items"] = parse_alink_list(alinks)

        # Product results
        text = get_text(sub, "div", {"class": re.compile("fG8Fp")}) or ""
        if not alinks and "$" in text:
            parsed["sub_type"] = "submenu_product"
            details.update(parse_product(text))
            details["type"] = "product"

    elif rating_span := sub.find("span", {"class": ["Y0A0hc", "z3HNkc"]}):
        # Modern rating widget (e.g. entertainment titles with star ratings)
        ratings = parse_rating_aria_label(str(rating_span.get("aria-label", "")))
        if ratings:
            details["type"] = "ratings"
            details.update(ratings)

    parsed["details"] = details if details else None
    return parsed


_ARIA_RATING_RE = re.compile(r"Rated\s+(\d+(?:\.\d+)?)\s+out of\s+(\d+)")
_ARIA_REVIEWS_RE = re.compile(r"\(([\d,]+)\)\s*user reviews?")


def parse_rating_aria_label(aria_label: str) -> dict:
    """Parse 'Rated 2.5 out of 5, (5,114) user reviews' into structured fields."""
    rating_match = _ARIA_RATING_RE.search(aria_label or "")
    if not rating_match:
        return {}
    result: dict = {
        "rating": float(rating_match.group(1)),
        "scale": int(rating_match.group(2)),
    }
    reviews_match = _ARIA_REVIEWS_RE.search(aria_label)
    if reviews_match:
        result["n_reviews"] = int(reviews_match.group(1).replace(",", ""))
    return result


def parse_ratings(text) -> dict:
    text = [t.strip() for t in text]
    numeric = re.compile(r"^\d*[.]?\d*$")
    rating = re.split("Rating: ", text[0])[-1]
    details: dict = {"rating": float(rating)} if numeric.match(rating) else {"rating": rating}

    if len(text) > 1:
        str_match_0 = re.compile(" vote[s]?| review[s]?")
        str_match_1 = re.compile("Review by")
        if str_match_0.search(text[1]):
            reviews = re.split(str_match_0, text[1])[0]
            reviews = reviews.replace(",", "")[1:]  # [1:] drops unicode char
            details["reviews"] = int(reviews)
        elif str_match_1.search(text[1]):
            details["reviews"] = 1

    return details


def parse_product(text: str) -> dict:
    split_match = re.compile("-|·")
    parts = re.split(split_match, text)
    if len(parts) == 1:
        return {"price": parts[0].strip()[1:]}
    return {"price": parts[0].strip()[1:], "stock": parts[1].strip()[1:]}


# General Video Results -----------------------------------------------------


def is_general_video(cmpt: bs4.element.Tag) -> bool:
    class_list = cmpt.get("class") or []
    return "PmEWq" in class_list


def parse_general_video(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    a = sub.select_one("a[href]")
    return {
        "type": "general",
        "sub_type": "video",
        "sub_rank": sub_rank,
        "title": get_result_text(sub, "h3.LC20lb"),
        "url": a.get("href", "") if a else None,
        "text": get_result_text(sub, ".ITZIwc"),
        "cite": get_result_text(sub, "cite", strip=False),
        "details": get_result_details(sub),
    }


def get_result_text(cmpt: bs4.element.Tag, selector: str, strip: bool = True) -> str | None:
    element = cmpt.select_one(selector)
    return element.get_text(strip=strip) if element else None


def get_result_details(cmpt: bs4.element.Tag) -> dict | None:
    source = get_result_text(cmpt, ".gqF9jc", strip=False)
    duration = get_result_text(cmpt, ".JIv15d")
    if source is None and duration is None:
        return None
    return {"type": "video", "source": source, "duration": duration}
