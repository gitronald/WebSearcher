"""Parse a Twitter carousel component.

A linked header (account or topic) plus a horizontal carousel of tweets;
each card has tweet text, source, and a deep-link URL.
"""

import re
from typing import Any

from selectolax.parser import Node

from .._slx import get_text
from ..utils import url_unquote


def parse_twitter_cards(cmpt) -> list:
    node: Node = cmpt
    parsed_header = parse_twitter_header(node)
    carousel = node.css_first("g-scrolling-carousel")
    subs = list(carousel.css("g-inner-card")) if carousel is not None else []
    parsed_cards = [parse_twitter_card(sub, sub_rank + 1) for sub_rank, sub in enumerate(subs)]
    return [parsed_header] + parsed_cards


def parse_twitter_header(node: Node, sub_rank: int = 0) -> dict:
    parsed: dict[str, Any] = {"type": "twitter_cards", "sub_type": "header", "sub_rank": sub_rank}
    element_current = node.css_first("g-link")
    element_legacy = node.css_first("h3.r")
    if node.css_first("h3") is not None:
        if element_legacy is not None:
            href = element_legacy.attributes.get("href", "")
            parsed["url"] = url_unquote(str(href)) if href else None
            parsed["title"] = get_text(element_legacy.css_first("a"), " ")
        elif element_current is not None:
            link = element_current.css_first("a")
            href = link.attributes.get("href") if link is not None else None
            parsed["url"] = url_unquote(str(href)) if href else None
            parsed["title"] = get_text(element_current, " ")
    elif element_current is not None:
        link = element_current.css_first("a")
        parsed["url"] = link.attributes.get("href") if link is not None else None
        parsed["title"] = get_text(element_current, " ")
    parsed["cite"] = get_text(node.css_first("cite"), " ")

    return parsed


def parse_twitter_card(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict[str, Any] = {"type": "twitter_cards", "sub_type": "card", "sub_rank": sub_rank}

    # Tweet account
    title = sub.css_first("g-link")
    parsed["title"] = get_text(title.css_first("a"), " ") if title is not None else None

    # Bottom div containing details
    div = sub.css_first("div.Brgz0")
    if div is not None:
        a = div.css_first("a")
        url = a.attributes.get("href") if a is not None else None
        parsed["url"] = url_unquote(url) if url else None
        parsed["text"] = get_text(div.css_first("div.xcQxib"), " ")
        parsed["cite"] = get_text(div.css_first("div.rmxqbe"), " ")

    # Single-account carousels carry no per-card account link; fall back to the
    # author handle from the tweet permalink (twitter.com/{handle}/status/...).
    if not parsed.get("title"):
        parsed["title"] = _handle_from_url(parsed.get("url"))

    return parsed


def _handle_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"(?:twitter|x)\.com/([^/?]+)/status/", url)
    return f"@{match.group(1)}" if match else None
