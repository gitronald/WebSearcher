"""Parse a "General" results component.

The ubiquitous blue-title / green-citation / black-summary results, sometimes
grouped into multi-result components with related themes. Subtypes include
submenus (rating, list, table, mini), scholarly results, products, and videos.
"""

import re

from selectolax.lexbor import LexborNode as Node

from .._slx import class_tokens, get_text


def parse_general_results(elem) -> list:
    node: Node = elem
    subs = find_subcomponents(node)
    return [parse_general_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def find_subcomponents(node: Node) -> list[Node]:
    self_id = node.mem_id
    # Standard format -- exclude self so a wrapping div.g doesn't match itself.
    subs = [n for n in node.css("div.g") if n.mem_id != self_id]
    if subs:
        parent_g = subs[0]  # first .g in document order
        # Nested .g dedup: if parent_g itself contains another .g descendant
        # (excluding parent_g itself), return only the outer wrapper.
        parent_id = parent_g.mem_id
        nested = next((n for n in parent_g.css("div.g") if n.mem_id != parent_id), None)
        if nested is not None:
            return [parent_g]
        return subs

    # Sub-results format (2023+)
    additional = [n for n in node.css("div.d4rhi") if n.mem_id != self_id]
    if additional:
        first = next((n for n in node.css("div") if n.mem_id != self_id), None)
        return [first] + additional if first is not None else additional

    # Video results
    subs = [n for n in node.css("div.PmEWq") if n.mem_id != self_id]
    if subs:
        return subs

    # Fallback: treat entire component as single result
    return [node]


def parse_general_result(sub: Node, sub_rank: int = 0) -> dict:
    if is_general_video(sub):
        return parse_general_video(sub, sub_rank=sub_rank)

    sub_id = sub.mem_id
    title_div = (
        next((n for n in sub.css("div.rc") if n.mem_id != sub_id), None)
        or next((n for n in sub.css("div.yuRUbf") if n.mem_id != sub_id), None)
    )
    body_div = (
        next((n for n in sub.css("span.st") if n.mem_id != sub_id), None)
        or next((n for n in sub.css("div.VwiC3b") if n.mem_id != sub_id), None)
    )

    title_h3 = title_div.css_first("h3") if title_div is not None else None
    title_a = title_div.css_first("a") if title_div is not None else None
    cite_el = next((n for n in sub.css("cite") if n.mem_id != sub_id), None)

    parsed: dict = {
        "type": "general",
        "sub_rank": sub_rank,
        "title": get_text(title_h3, " ") if title_h3 is not None else None,
        "url": title_a.attributes.get("href") if title_a is not None else None,
        "text": get_text(body_div, " ") if body_div is not None else None,
        "cite": get_text(cite_el, " ") if cite_el is not None else None,
    }

    if parsed["title"] is None and parsed["url"] is None:
        parsed["error"] = "no title or url"

    return parse_subtype_details(sub, parsed)


def parse_alink(a: Node) -> dict:
    return {"url": a.attributes["href"], "text": get_text(a) or ""}


def parse_alink_list(alinks) -> list:
    items = []
    for a in alinks:
        if a.tag and not a.tag.startswith("-") and "href" in a.attributes:
            items.append(parse_alink(a))
    return items


def parse_subtype_details(sub: Node, parsed: dict) -> dict:
    details: dict = {}

    # If top menu with children, ignore URLs and get correct title URL.
    top_menu = sub.css_first("div.yWc32e")
    if top_menu is not None:
        children = list(top_menu.iter(include_text=False))
        if children:
            for child in children:
                child.decompose()
            h3 = sub.css_first("h3")
            if h3 is not None:
                a = h3.css_first("a")
                if a is not None:
                    parsed["url"] = a.attributes["href"]

    sub_classes = class_tokens(sub)
    if "d4rhi" in sub_classes:
        parsed["sub_type"] = "subresult"

    elif sub.css_first("div.d86Vh") is not None:
        # Image thumbnail strip (e.g. Pinterest board, Etsy market, shop pages):
        # a horizontal row of g-img previews that all link back to the result.
        # The thumbnails are JS-driven data: placeholders with no per-image url
        # or alt text, so only the layout is flagged -- there is nothing that
        # fits an existing details schema to capture.
        parsed["sub_type"] = "image_strip"

    elif (stars := sub.css_first("g-review-stars")) is not None:
        # Submenu - rating
        parsed["sub_type"] = "submenu_rating"
        sibling = _next_sibling_with_text(stars)
        if sibling is not None:
            text = str(sibling).strip()
            if len(text):
                ratings = parse_ratings(text.split("-"))
                details.update(ratings)
                details["type"] = "review"

    elif (submenu_div := sub.css_first("div.P1usbc, div.IThcWe")) is not None:
        # Submenu - list format
        parsed["sub_type"] = "submenu"
        alinks = list(submenu_div.css("a"))
        details["type"] = "hyperlinks"
        details["items"] = parse_alink_list(alinks)

    elif (table := sub.css_first("table")) is not None:
        # Submenu - table format
        parsed["sub_type"] = "submenu"
        alinks = list(table.css("a"))
        details["type"] = "hyperlinks"
        details["items"] = parse_alink_list(alinks)

    elif (submenu := sub.css_first("div.osl, div.jYOxx")) is not None:
        # Mini submenu
        parsed["sub_type"] = "submenu_mini"
        alinks = list(submenu.css("a"))
        details["type"] = "hyperlinks"
        details["items"] = parse_alink_list(alinks)

    elif (scholar_div := sub.css_first('div[class*="fG8Fp"]')) is not None:
        # bs4 ``find("div", {"class": re.compile("fG8Fp")})`` is regex substring
        # match; CSS ``[class*="fG8Fp"]`` is the same substring semantics here.
        alinks = list(scholar_div.css("a"))
        if alinks and "Cited by" in (get_text(alinks[0]) or ""):
            # Scholar results
            parsed["sub_type"] = "submenu_scholarly"
            details["type"] = "hyperlinks"
            details["items"] = parse_alink_list(alinks)

        # Product results
        text = get_text(scholar_div, " ") or ""
        if not alinks and "$" in text:
            parsed["sub_type"] = "submenu_product"
            details.update(parse_product(text))
            details["type"] = "product"

    elif (rating_span := sub.css_first("span.Y0A0hc, span.z3HNkc")) is not None:
        # Modern rating widget (e.g. entertainment titles with star ratings)
        ratings = parse_rating_aria_label(str(rating_span.attributes.get("aria-label", "")))
        if ratings:
            details["type"] = "ratings"
            details.update(ratings)

    parsed["details"] = details if details else None
    return parsed


def _next_sibling_with_text(node: Node) -> Node | None:
    """bs4 ``.next_sibling`` semantics: returns the next sibling INCLUDING text
    nodes (selectolax ``.next`` may skip text)."""
    parent = node.parent
    if parent is None:
        return None
    siblings = list(parent.iter(include_text=True))
    node_id = node.mem_id
    for i, sib in enumerate(siblings):
        if sib.mem_id == node_id and i + 1 < len(siblings):
            return siblings[i + 1]
    return None


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


def is_general_video(cmpt: Node) -> bool:
    return "PmEWq" in class_tokens(cmpt)


def parse_general_video(sub: Node, sub_rank: int = 0) -> dict:
    a = sub.css_first("a[href]")
    title_el = sub.css_first("h3.LC20lb")
    body_el = sub.css_first(".ITZIwc")
    cite_el = sub.css_first("cite")
    return {
        "type": "general",
        "sub_type": "video",
        "sub_rank": sub_rank,
        "title": get_text(title_el, strip=True) if title_el is not None else None,
        "url": a.attributes.get("href", "") if a is not None else None,
        "text": get_text(body_el, strip=True) if body_el is not None else None,
        "cite": get_text(cite_el, strip=False) if cite_el is not None else None,
        "details": get_result_details(sub),
    }


def get_result_details(cmpt: Node) -> dict | None:
    source_el = cmpt.css_first(".gqF9jc")
    duration_el = cmpt.css_first(".JIv15d")
    source = get_text(source_el, strip=False) if source_el is not None else None
    duration = get_text(duration_el, strip=True) if duration_el is not None else None
    if source is None and duration is None:
        return None
    return {"type": "video", "source": source, "duration": duration}
