"""Parse the Recipes carousel component.

A horizontal carousel of recipe cards. Each card links to a recipe and carries
a title, the source publisher, an optional rating + review count, an optional
cook time, and an ingredient summary. Without a dedicated parser the whole
carousel collapses into a single ``<|>``-joined text blob, so we split each
card into ``title`` / ``url`` plus a ``ratings`` details block.
"""

import re

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text

_CARD_CLASS = "a-no-hover-decoration"
# Async-loaded ("Popular recipes") carousel: each card is a div wrapping a title
# div plus a separate result anchor (the title is not inside the anchor).
_CARD_CLASS_ASYNC = "XDOVcf"
_TITLE_CLASS = "hfac6d"
_SOURCE_CLASS = "g6wEbd"
_DURATION_CLASS = "z8gr9e"
_INGREDIENTS_CLASS = "LDr9cf"
_RATING_CLASS = "z3HNkc"
_RATING_TEXT_CLASS = "yi40Hd"
_N_REVIEWS_CLASS = "RDApEe"


def parse_recipes(elem) -> list:
    node: Node = elem
    cards = list(node.css(f"a.{_CARD_CLASS}"))
    if not cards:
        cards = [a for a in node.css("a[href]") if a.css_first(f"div.{_TITLE_CLASS}") is not None]
    if not cards:
        cards = list(node.css(f"div.{_CARD_CLASS_ASYNC}"))
    return [_parse_card(card, sub_rank) for sub_rank, card in enumerate(cards)]


def _parse_card(card: Node, sub_rank: int = 0) -> dict:
    href = card.attributes.get("href")
    if not href:
        # Async variant: the card is a wrapper div, url is on an inner anchor.
        anchor = card.css_first("a[href]")
        href = anchor.attributes.get("href") if anchor is not None else None
    parsed: dict = {
        "type": "recipes",
        "sub_rank": sub_rank,
        "title": _text(card, _TITLE_CLASS),
        "url": str(href) if href else None,
        "text": None,
        "cite": None,
    }

    details: dict = {"type": "ratings"}
    source = _text(card, _SOURCE_CLASS)
    if source:
        details["source"] = source
    rating = _rating(card)
    if rating is not None:
        details["rating"] = rating
    n_reviews = _n_reviews(card)
    if n_reviews is not None:
        details["n_reviews"] = n_reviews
    duration = _text(card, _DURATION_CLASS)
    if duration:
        details["duration"] = duration
    ingredients = _text(card, _INGREDIENTS_CLASS)
    if ingredients:
        details["ingredients"] = ingredients

    parsed["details"] = details if len(details) > 1 else None
    return parsed


def _text(card: Node, class_: str) -> str | None:
    div = card.css_first(f"div.{class_}")
    if div is None:
        return None
    text = get_text(div, " ", strip=True)
    return text or None


def _rating(card: Node) -> str | None:
    """Read the rating from the ``z3HNkc`` aria-label, falling back to text."""
    span = card.css_first(f"span.{_RATING_CLASS}")
    if span is not None and span.attributes.get("aria-label"):
        match = re.search(r"[\d.]+", str(span.attributes["aria-label"]))
        if match:
            return match.group()
    span = card.css_first(f"span.{_RATING_TEXT_CLASS}")
    if span is not None:
        text = get_text(span, strip=True)
        return text or None
    return None


def _n_reviews(card: Node) -> str | None:
    span = card.css_first(f"span.{_N_REVIEWS_CLASS}")
    if span is None:
        return None
    text = (get_text(span, strip=True) or "").strip("()")
    return text or None
