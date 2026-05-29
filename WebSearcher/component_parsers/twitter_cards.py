"""Parse a Twitter carousel component.

A linked header (account or topic) plus a horizontal carousel of tweets;
each card has tweet text, source, and a deep-link URL.
"""

import re
from typing import Any

from selectolax.parser import Node

from ..utils import get_link, get_text, url_unquote


def parse_twitter_cards(cmpt: Node) -> list:
    parsed_header = parse_twitter_header(cmpt)
    carousel = cmpt.find("g-scrolling-carousel")
    subs = carousel.find_all("g-inner-card") if carousel else []
    parsed_cards = [parse_twitter_card(sub, sub_rank + 1) for sub_rank, sub in enumerate(subs)]
    return [parsed_header] + parsed_cards


def parse_twitter_header(cmpt: Node, sub_rank: int = 0) -> dict:
    parsed: dict[str, Any] = {"type": "twitter_cards", "sub_type": "header", "sub_rank": sub_rank}
    element_current = cmpt.find("g-link")
    element_legacy = cmpt.find("h3", {"class": "r"})
    if cmpt.find("h3"):
        if element_legacy:
            href = element_legacy.get("href", "")
            parsed["url"] = url_unquote(str(href)) if href else None
            parsed["title"] = get_text(element_legacy, "a")
        elif element_current:
            link = get_link(element_current)
            parsed["url"] = url_unquote(link) if link else None
            parsed["title"] = get_text(element_current)
    elif element_current:
        parsed["url"] = get_link(element_current)
        parsed["title"] = get_text(element_current)
    parsed["cite"] = get_text(cmpt, "cite")

    return parsed


def parse_twitter_card(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict[str, Any] = {"type": "twitter_cards", "sub_type": "card", "sub_rank": sub_rank}

    # Tweet account
    title = sub.find("g-link")
    parsed["title"] = get_text(title, "a") if title else None

    # Bottom div containing details
    div = sub.find("div", {"class": "Brgz0"})
    if div:
        url = get_link(div)
        parsed["url"] = url_unquote(url) if url else None
        parsed["text"] = get_text(div, "div", {"class": "xcQxib"})
        parsed["cite"] = get_text(div, "div", {"class": "rmxqbe"})

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
