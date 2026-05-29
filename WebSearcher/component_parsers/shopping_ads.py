"""Parse a shopping-ads component.

Two layouts: the standard product-listing-ads grid (pla-unit) and the
sponsored hotel carousel (role=listitem cards from atvcap). Each card
captures price, source, rating, review count, stars, and amenity tags.
"""

from selectolax.parser import Node

from .._slx import class_tokens, get_text


def parse_shopping_ads(cmpt) -> list:
    node: Node = cmpt.raw
    # Sponsored hotel carousel (atvcap)
    cards = list(node.css('[role="listitem"]'))
    if cards:
        return [_parse_sponsored_hotel(card, i) for i, card in enumerate(cards)]

    # Standard product listing ads (legacy mnr-c pla-unit wrapper). bs4
    # ``find_all("div", {"class": "mnr-c pla-unit"})`` is an EXACT multi-token
    # match (not AND-of-tokens), so a div with class ``"mnr-c c3mZkd pla-unit"``
    # must NOT match -- it would route a modern PLA card through the legacy
    # parser that lacks the aria-label fallback. Narrow with the compound CSS
    # then verify exact class-token list.
    _legacy = ["mnr-c", "pla-unit"]
    subs = [
        d
        for d in node.css("div.mnr-c.pla-unit")
        if d.mem_id != node.mem_id and class_tokens(d) == _legacy
    ]
    if subs:
        return [_parse_pla_unit(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    # Modern PLA: each product is a clickable-card anchor (no mnr-c wrapper).
    cards = list(node.css("a.clickable-card"))
    return [_parse_pla_card(card, sub_rank) for sub_rank, card in enumerate(cards)]


def _parse_pla_unit(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "shopping_ads", "sub_rank": sub_rank}
    card = sub.css_first("a.clickable-card")
    if card is not None:
        parsed["url"] = card.attributes["href"]
        parsed["title"] = card.attributes["aria-label"]
    return parsed


def _parse_pla_card(card: Node, sub_rank: int = 0) -> dict:
    """Parse a modern product-listing-ad card (``a.clickable-card``).

    Title comes from the card's ``aria-label`` (full product name) with the
    truncated ``span.pymv4e`` as fallback; price/source/review count are read
    from the surrounding ``div.pla-unit`` into a ``ratings`` details block.
    """
    # bs4 ``card.find_parent("div", {"class": "pla-unit"}) or card``: walk
    # ancestors only (never self), match on tag+class-token.
    unit: Node = card
    p = card.parent
    while p is not None:
        if p.tag == "div" and "pla-unit" in class_tokens(p):
            unit = p
            break
        p = p.parent

    title = card.attributes.get("aria-label") or _card_text(unit, "span.pymv4e")
    parsed: dict = {
        "type": "shopping_ads",
        "sub_type": "product",
        "sub_rank": sub_rank,
        "title": title or None,
        "url": card.attributes.get("href"),
        "text": None,
        "cite": None,
    }

    details: dict = {"type": "ratings"}
    price = _card_text(unit, "span.e10twf")
    if price:
        details["price"] = price
    source = _card_text(unit, "span.zPEcBd")
    if source:
        details["source"] = source
    n_reviews = _card_text(unit, "span.pbAs0b")
    if n_reviews:
        details["n_reviews"] = n_reviews.strip("()")

    parsed["details"] = details if len(details) > 1 else None
    return parsed


def _card_text(node: Node, css: str) -> str | None:
    text = get_text(node.css_first(css), " ", strip=True)
    return text or None


def _parse_sponsored_hotel(card: Node, sub_rank: int = 0) -> dict:
    name_div = card.css_first("div.KZYtMc")
    price_div = card.css_first("div.XO8mWb")
    source_div = card.css_first("div.sX5I1c")
    rating_span = card.css_first("span.Y0A0hc")

    # Star level and amenity are in role=text spans
    role_texts = list(card.css('span[role="text"].cHaqb'))
    stars = get_text(role_texts[0], strip=True) if len(role_texts) > 0 else None
    amenity = get_text(role_texts[1], strip=True) if len(role_texts) > 1 else None

    # Rating text includes review count (e.g. "3.2(345)")
    rating_text = get_text(rating_span, strip=True) if rating_span is not None else None
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
    if price_div is not None:
        details["price"] = get_text(price_div, strip=True)
    if source_div is not None:
        details["source"] = get_text(source_div, strip=True)
    if rating is not None:
        details["rating"] = rating
    if n_reviews is not None:
        details["n_reviews"] = n_reviews
    if stars:
        details["stars"] = stars
    if amenity:
        details["amenity"] = amenity

    a = card.css_first("a[href]")
    return {
        "type": "shopping_ads",
        "sub_type": "hotels",
        "sub_rank": sub_rank,
        "title": get_text(name_div, strip=True) if name_div is not None else None,
        "url": a.attributes.get("href") if a is not None else None,
        "text": None,
        "cite": None,
        "details": details if details else None,
    }
