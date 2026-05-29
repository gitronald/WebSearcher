"""Parse a locations component.

Currently handles hotel listings: each item is an anchor pointing to a
/travel/ URL with a name, price, rating, review count, star rating, and
short description.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text


def parse_locations(cmpt) -> list:
    node: Node = cmpt
    sub_type = classify_locations_sub_type(node)
    if sub_type == "hotels":
        return parse_hotels(node)
    return [{"type": "locations", "sub_rank": 0, "error": f"unknown sub_type: {sub_type}"}]


def classify_locations_sub_type(node: Node) -> str:
    heading = node.css_first('[role="heading"]')
    if heading is not None:
        text = get_text(heading, strip=True) or ""
        if "Hotels" in text or "Hotel" in text:
            return "hotels"
    # Fallback: any /travel/ link present
    for a in node.css("a[href]"):
        if "/travel/" in (a.attributes.get("href") or ""):
            return "hotels"
    return "unknown"


def parse_hotels(node: Node) -> list:
    items: list = []
    for a in node.css("a[href]"):
        href = a.attributes.get("href") or ""
        if "/travel/" not in href:
            continue
        name_div = a.css_first("div.sxdlOc") or a.css_first("div.BTPx6e")
        if name_div is None:
            continue
        items.append(_parse_hotel_item(a, len(items)))

    if not items:
        return [
            {
                "type": "locations",
                "sub_type": "hotels",
                "sub_rank": 0,
                "error": "no hotel items found",
            }
        ]
    return items


def _parse_hotel_item(a: Node, sub_rank: int) -> dict:
    name_div = a.css_first("div.sxdlOc") or a.css_first("div.BTPx6e")
    price_span = a.css_first("span.sRlU8b")
    rating_span = a.css_first("span.yi40Hd")
    reviews_span = a.css_first("span.RDApEe")
    stars_span = a.css_first("span.NAkmnc")
    desc_div = a.css_first("div.S7Ajc")

    return {
        "type": "locations",
        "sub_type": "hotels",
        "sub_rank": sub_rank,
        "title": get_text(name_div, strip=True) if name_div is not None else None,
        "url": a.attributes.get("href"),
        "text": get_text(desc_div, strip=True) if desc_div is not None else None,
        "cite": None,
        "details": _parse_hotel_details(price_span, rating_span, reviews_span, stars_span),
    }


def _parse_hotel_details(
    price_span: Node | None,
    rating_span: Node | None,
    reviews_span: Node | None,
    stars_span: Node | None,
) -> dict | None:
    details: dict = {}
    if price_span is not None:
        details["price"] = get_text(price_span, strip=True)
    if rating_span is not None:
        details["rating"] = get_text(rating_span, strip=True)
    if reviews_span is not None:
        details["reviews"] = get_text(reviews_span, strip=True)
    if stars_span is not None:
        details["stars"] = get_text(stars_span, strip=True)
    return details if details else None
