"""Parse a shopping-ads component.

Two layouts: the standard product-listing-ads grid (pla-unit) and the
sponsored hotel carousel (role=listitem cards from atvcap). Each card
captures price, source, rating, review count, stars, and amenity tags.
"""

from selectolax.parser import Node


def parse_shopping_ads(cmpt: Node) -> list:
    # Sponsored hotel carousel (atvcap)
    cards = cmpt.find_all(attrs={"role": "listitem"})
    if cards:
        return [_parse_sponsored_hotel(card, i) for i, card in enumerate(cards)]

    # Standard product listing ads (legacy mnr-c pla-unit wrapper)
    subs = cmpt.find_all("div", {"class": "mnr-c pla-unit"})
    if subs:
        return [_parse_pla_unit(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    # Modern PLA: each product is a clickable-card anchor (no mnr-c wrapper).
    cards = cmpt.find_all("a", {"class": "clickable-card"})
    return [_parse_pla_card(card, sub_rank) for sub_rank, card in enumerate(cards)]


def _parse_pla_unit(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "shopping_ads", "sub_rank": sub_rank}
    card = sub.find("a", {"class": "clickable-card"})
    if card:
        parsed["url"] = card["href"]
        parsed["title"] = card["aria-label"]
    return parsed


def _parse_pla_card(card: Node, sub_rank: int = 0) -> dict:
    """Parse a modern product-listing-ad card (``a.clickable-card``).

    Title comes from the card's ``aria-label`` (full product name) with the
    truncated ``span.pymv4e`` as fallback; price/source/review count are read
    from the surrounding ``div.pla-unit`` into a ``ratings`` details block.
    """
    unit = card.find_parent("div", {"class": "pla-unit"}) or card

    title = card.get("aria-label") or _card_text(unit, "span", "pymv4e")
    parsed: dict = {
        "type": "shopping_ads",
        "sub_type": "product",
        "sub_rank": sub_rank,
        "title": title or None,
        "url": card.get("href"),
        "text": None,
        "cite": None,
    }

    details: dict = {"type": "ratings"}
    price = _card_text(unit, "span", "e10twf")
    if price:
        details["price"] = price
    source = _card_text(unit, "span", "zPEcBd")
    if source:
        details["source"] = source
    n_reviews = _card_text(unit, "span", "pbAs0b")
    if n_reviews:
        details["n_reviews"] = n_reviews.strip("()")

    parsed["details"] = details if len(details) > 1 else None
    return parsed


def _card_text(node: Node, tag: str, class_: str) -> str | None:
    el = node.find(tag, {"class": class_})
    if el is None:
        return None
    text = el.get_text(" ", strip=True)
    return text or None


def _parse_sponsored_hotel(card: Node, sub_rank: int = 0) -> dict:
    name_div = card.find("div", {"class": "KZYtMc"})
    price_div = card.find("div", {"class": "XO8mWb"})
    source_div = card.find("div", {"class": "sX5I1c"})
    rating_span = card.find("span", {"class": "Y0A0hc"})

    # Star level and amenity are in role=text spans
    role_texts = card.find_all("span", {"role": "text", "class": "cHaqb"})
    stars = role_texts[0].get_text(strip=True) if len(role_texts) > 0 else None
    amenity = role_texts[1].get_text(strip=True) if len(role_texts) > 1 else None

    # Rating text includes review count (e.g. "3.2(345)")
    rating_text = rating_span.get_text(strip=True) if rating_span else None
    rating = None
    n_reviews = None
    if rating_text:
        paren = rating_text.find("(")
        if paren > 0:
            rating = rating_text[:paren]
            n_reviews = rating_text[paren:].strip("()")
        else:
            rating = rating_text

    details: dict = {"type": "ratings"}
    if price_div:
        details["price"] = price_div.get_text(strip=True)
    if source_div:
        details["source"] = source_div.get_text(strip=True)
    if rating is not None:
        details["rating"] = rating
    if n_reviews is not None:
        details["n_reviews"] = n_reviews
    if stars:
        details["stars"] = stars
    if amenity:
        details["amenity"] = amenity

    a = card.find("a", href=True)
    return {
        "type": "shopping_ads",
        "sub_type": "hotels",
        "sub_rank": sub_rank,
        "title": name_div.get_text(strip=True) if name_div else None,
        "url": a.get("href") if a else None,
        "text": None,
        "cite": None,
        "details": details if details else None,
    }
