"""Parse the Recipes carousel component.

A horizontal carousel of recipe cards. Each card links to a recipe and carries
a title, the source publisher, an optional rating + review count, an optional
cook time, and an ingredient summary. Without a dedicated parser the whole
carousel collapses into a single ``<|>``-joined text blob, so we split each
card into ``title`` / ``url`` plus a ``ratings`` details block.
"""

import re

from .._slx import SoupNode as Node

_CARD_CLASS = "a-no-hover-decoration"
_TITLE_CLASS = "hfac6d"
_SOURCE_CLASS = "g6wEbd"
_DURATION_CLASS = "z8gr9e"
_INGREDIENTS_CLASS = "LDr9cf"
_RATING_CLASS = "z3HNkc"
_RATING_TEXT_CLASS = "yi40Hd"
_N_REVIEWS_CLASS = "RDApEe"


def parse_recipes(cmpt: Node) -> list:
    cards = cmpt.find_all("a", {"class": _CARD_CLASS})
    if not cards:
        cards = [a for a in cmpt.find_all("a", href=True) if a.find("div", {"class": _TITLE_CLASS})]
    return [_parse_card(card, sub_rank) for sub_rank, card in enumerate(cards)]


def _parse_card(card: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {
        "type": "recipes",
        "sub_rank": sub_rank,
        "title": _text(card, _TITLE_CLASS),
        "url": str(card["href"]) if card.get("href") else None,
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
    div = card.find("div", {"class": class_})
    if div is None:
        return None
    text = div.get_text(" ", strip=True)
    return text or None


def _rating(card: Node) -> str | None:
    """Read the rating from the ``z3HNkc`` aria-label, falling back to text."""
    span = card.find("span", {"class": _RATING_CLASS})
    if span is not None and span.get("aria-label"):
        match = re.search(r"[\d.]+", str(span["aria-label"]))
        if match:
            return match.group()
    span = card.find("span", {"class": _RATING_TEXT_CLASS})
    if span is not None:
        text = span.get_text(strip=True)
        return text or None
    return None


def _n_reviews(card: Node) -> str | None:
    span = card.find("span", {"class": _N_REVIEWS_CLASS})
    if span is None:
        return None
    text = span.get_text(strip=True).strip("()")
    return text or None
