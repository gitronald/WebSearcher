"""Parse a locations component.

Currently handles hotel listings: each item is an anchor pointing to a
/travel/ URL with a name, price, rating, review count, star rating, and
short description.
"""

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text
from ...models.data import ERR_NO_HOTELS, ERR_UNKNOWN_SUBTYPE, error_details


def parse_locations(elem) -> list:
    node: Node = elem
    sub_type = classify_locations_sub_type(node)
    if sub_type == "hotels":
        return parse_hotels(node)
    return [
        {
            "type": "locations",
            "sub_rank": 0,
            "details": error_details(f"{ERR_UNKNOWN_SUBTYPE}: {sub_type}"),
        }
    ]


def classify_locations_sub_type(node: Node) -> str:
    if node.css_first('a[href*="/local/places/hotel/"]') is not None:
        return "hotels"
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

    # Card carousel variant ("Similar to <hotel>" / "Popular hotels in <place>"):
    # per card one name span and one local/places anchor, siblings inside the
    # card wrapper (the anchor is an overlay, not the content container), and
    # no /travel/ item links. Walk up from each name span to the smallest
    # wrapper that also holds the card's anchor.
    if not items:
        seen_cards: set[int] = set()
        for name_span in node.css("span.Yt787"):
            card = name_span.parent
            for _ in range(6):
                if card is None:
                    break
                if card.css_first('a[href*="/local/places/hotel/"]') is not None:
                    break
                card = card.parent
            if card is None or card.mem_id in seen_cards:
                continue
            if card.css_first('a[href*="/local/places/hotel/"]') is None:
                continue
            seen_cards.add(card.mem_id)
            items.append(_parse_hotel_card(card, name_span, len(items)))

    if not items:
        return [
            {
                "type": "locations",
                "sub_type": "hotels",
                "sub_rank": 0,
                "details": error_details(ERR_NO_HOTELS),
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


def _parse_hotel_card(card: Node, name_span: Node, sub_rank: int) -> dict:
    a = card.css_first('a[href*="/local/places/hotel/"]')
    price_span = card.css_first("span.rDUZLd")
    rating_span = card.css_first("span.yi40Hd")
    reviews_span = card.css_first("span.RDApEe")

    return {
        "type": "locations",
        "sub_type": "hotels",
        "sub_rank": sub_rank,
        "title": get_text(name_span, strip=True),
        "url": a.attributes.get("href") if a is not None else None,
        "text": None,
        "cite": None,
        "details": _parse_hotel_details(price_span, rating_span, reviews_span, None),
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
