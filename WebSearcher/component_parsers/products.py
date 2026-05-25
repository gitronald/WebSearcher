"""Parse a "Products" component.

Two organic shopping layouts that previously slipped into the ``general``
parser and emitted hollow "no title or url" rows:

- ``grid``  - immersive popular-products grid; each product is a
  ``data-attrid="apg-product-result"`` card with a name, price, store, and
  rating but **no link** (the cards are JS-driven).
- ``brands`` - "Explore brands" merchant carousel; each card links to a
  merchant site and carries a store rating and review count.

Price / store / rating are captured in a ``ratings`` details block, reusing the
schema produced by :mod:`WebSearcher.component_parsers.shopping_ads`.
"""

import re

import bs4

_PRICE_RE = re.compile(r"\$[\d,]+(?:\.\d+)?")


def parse_products(cmpt: bs4.element.Tag) -> list:
    # Family B: immersive product grid (apg-product-result cards, no links)
    grid_cards = cmpt.find_all(attrs={"data-attrid": "apg-product-result"})
    if grid_cards:
        return [_parse_grid_card(card, i) for i, card in enumerate(grid_cards)]

    # Family A: "Explore brands" merchant carousel
    brand_cards = cmpt.find_all("div", {"class": "gON1yc"})
    if brand_cards:
        return [_parse_brand_card(card, i) for i, card in enumerate(brand_cards)]

    return []


def _parse_grid_card(card: bs4.element.Tag, sub_rank: int = 0) -> dict:
    title = _img_alt(card) or _text(card, "div", "gkQHve")

    parsed: dict = {
        "type": "products",
        "sub_type": "grid",
        "sub_rank": sub_rank,
        "title": title or None,
        "url": None,  # JS-driven cards carry no href
        "text": None,
        "cite": _text(card, "span", "WJMUdc"),  # store / merchant name
    }

    details: dict = {"type": "ratings"}
    price = _text(card, "span", "lmQWe") or _first_price(card)
    if price:
        details["price"] = price
    source = parsed["cite"]
    if source:
        details["source"] = source
    rating = _text(card, "span", "yi40Hd")
    if rating:
        details["rating"] = rating
    n_reviews = _text(card, "span", "RDApEe")
    if n_reviews:
        details["n_reviews"] = n_reviews.strip("()")

    parsed["details"] = details if len(details) > 1 else None
    return parsed


def _parse_brand_card(card: bs4.element.Tag, sub_rank: int = 0) -> dict:
    link = card.find("a", {"class": "J0tlkf"})
    brand = _text(card, "span", "V8apnb") or _img_alt(card)

    parsed: dict = {
        "type": "products",
        "sub_type": "brands",
        "sub_rank": sub_rank,
        "title": brand or None,
        "url": link["href"] if link and link.get("href") else None,
        "text": _text(card, "div", "dw0Zb"),
        "cite": None,
    }

    details: dict = {"type": "ratings"}
    rating = _text(card, "span", "yi40Hd")
    if rating:
        details["rating"] = rating
    n_reviews = _text(card, "span", "ZRQmE")
    if n_reviews:
        details["n_reviews"] = n_reviews.strip("()")

    parsed["details"] = details if len(details) > 1 else None
    return parsed


def _text(node: bs4.element.Tag, tag: str, class_: str) -> str | None:
    el = node.find(tag, {"class": class_})
    if el is None:
        return None
    text = el.get_text(" ", strip=True)
    return text or None


def _img_alt(node: bs4.element.Tag) -> str | None:
    img = node.find("img", alt=True)
    if img is None:
        return None
    alt = img.get("alt")
    if isinstance(alt, list):
        alt = " ".join(alt)
    alt = (alt or "").strip()
    return alt or None


def _first_price(card: bs4.element.Tag) -> str | None:
    match = _PRICE_RE.search(card.get_text(" ", strip=True))
    return match.group(0) if match else None
