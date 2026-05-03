"""Parser for locations components (hotels, etc.)"""

import bs4


def parse_locations(cmpt: bs4.element.Tag) -> list:
    """Parse a locations component (e.g. hotel listings)"""

    sub_type = classify_locations_sub_type(cmpt)
    if sub_type == "hotels":
        return parse_hotels(cmpt)
    return [{"type": "locations", "sub_rank": 0, "error": f"unknown sub_type: {sub_type}"}]


def classify_locations_sub_type(cmpt: bs4.element.Tag) -> str:
    """Classify the sub-type of a locations component"""
    heading = cmpt.find(attrs={"role": "heading"})
    if heading:
        text = heading.get_text(strip=True)
        if "Hotels" in text or "Hotel" in text:
            return "hotels"
    # Check for /travel/ links as fallback
    if cmpt.find("a", href=lambda h: h and "/travel/" in h):
        return "hotels"
    return "unknown"


def parse_hotels(cmpt: bs4.element.Tag) -> list:
    """Parse hotel items from a locations component"""

    items = []
    for a in cmpt.find_all("a", href=True):
        href = a.get("href") or ""
        if "/travel/" not in href:
            continue
        name_div = a.find("div", {"class": "sxdlOc"}) or a.find("div", {"class": "BTPx6e"})
        if not name_div:
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


def _parse_hotel_item(a: bs4.element.Tag, sub_rank: int) -> dict:
    """Parse a single hotel item from an anchor tag"""
    name_div = a.find("div", {"class": "sxdlOc"}) or a.find("div", {"class": "BTPx6e"})
    price_span = a.find("span", {"class": "sRlU8b"})
    rating_span = a.find("span", {"class": "yi40Hd"})
    reviews_span = a.find("span", {"class": "RDApEe"})
    stars_span = a.find("span", {"class": "NAkmnc"})
    desc_div = a.find("div", {"class": "S7Ajc"})

    return {
        "type": "locations",
        "sub_type": "hotels",
        "sub_rank": sub_rank,
        "title": name_div.get_text(strip=True) if name_div else None,
        "url": a.get("href"),
        "text": desc_div.get_text(strip=True) if desc_div else None,
        "cite": None,
        "details": _parse_hotel_details(price_span, rating_span, reviews_span, stars_span),
    }


def _parse_hotel_details(price_span, rating_span, reviews_span, stars_span) -> dict | None:
    """Extract hotel metadata"""
    details = {}
    if price_span:
        details["price"] = price_span.get_text(strip=True)
    if rating_span:
        details["rating"] = rating_span.get_text(strip=True)
    if reviews_span:
        details["reviews"] = reviews_span.get_text(strip=True)
    if stars_span:
        details["stars"] = stars_span.get_text(strip=True)
    return details if details else None
