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

from selectolax.parser import Node

from .._slx import get_text

_PRICE_RE = re.compile(r"\$[\d,]+(?:\.\d+)?")


def parse_products(cmpt) -> list:
    node: Node = cmpt
    # Family B: immersive product grid (no links). Modern cards are
    # data-attrid="apg-product-result"; older cards are g-inner-card. Both use
    # the same inner field classes, so _parse_grid_card handles either.
    grid_cards = list(node.css('[data-attrid="apg-product-result"]'))
    if not grid_cards:
        grid_cards = list(node.css("g-inner-card"))
    if grid_cards:
        return [_parse_grid_card(card, i) for i, card in enumerate(grid_cards)]

    # Family A: "Explore brands" merchant carousel
    brand_cards = list(node.css("div.gON1yc"))
    if brand_cards:
        return [_parse_brand_card(card, i) for i, card in enumerate(brand_cards)]

    return []


def _parse_grid_card(card: Node, sub_rank: int = 0) -> dict:
    title = _img_alt(card) or _text(card, "div.gkQHve")

    parsed: dict = {
        "type": "products",
        "sub_type": "grid",
        "sub_rank": sub_rank,
        "title": title or None,
        "url": None,  # JS-driven cards carry no href
        "text": None,
        "cite": _text(card, "span.WJMUdc"),  # store / merchant name
    }

    details: dict = {"type": "ratings"}
    price = _text(card, "span.lmQWe") or _first_price(card)
    if price:
        details["price"] = price
    source = parsed["cite"]
    if source:
        details["source"] = source
    rating = _text(card, "span.yi40Hd")
    if rating:
        details["rating"] = rating
    n_reviews = _text(card, "span.RDApEe")
    if n_reviews:
        details["n_reviews"] = n_reviews.strip("()")

    parsed["details"] = details if len(details) > 1 else None
    return parsed


def _parse_brand_card(card: Node, sub_rank: int = 0) -> dict:
    link = card.css_first("a.J0tlkf")
    brand = _text(card, "span.V8apnb") or _img_alt(card)

    parsed: dict = {
        "type": "products",
        "sub_type": "brands",
        "sub_rank": sub_rank,
        "title": brand or None,
        "url": link.attributes.get("href") if link is not None else None,
        "text": _text(card, "div.dw0Zb"),
        "cite": None,
    }

    details: dict = {"type": "ratings"}
    rating = _text(card, "span.yi40Hd")
    if rating:
        details["rating"] = rating
    n_reviews = _text(card, "span.ZRQmE")
    if n_reviews:
        details["n_reviews"] = n_reviews.strip("()")

    parsed["details"] = details if len(details) > 1 else None
    return parsed


def _text(node: Node, css: str) -> str | None:
    text = get_text(node.css_first(css), " ", strip=True)
    return text or None


def _img_alt(node: Node) -> str | None:
    img = node.css_first("img[alt]")
    if img is None:
        return None
    alt = img.attributes.get("alt") or ""
    return alt.strip() or None


def _first_price(card: Node) -> str | None:
    text = get_text(card, " ", strip=True) or ""
    match = _PRICE_RE.search(text)
    return match.group(0) if match else None
