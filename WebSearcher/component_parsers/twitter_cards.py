"""Parse a Twitter carousel component.

A linked header (account or topic) plus a horizontal carousel of tweets;
each card has tweet text, source, and a deep-link URL.
"""

from typing import Any

import bs4

from .. import utils


def parse_twitter_cards(cmpt: bs4.element.Tag) -> list:
    parsed_header = parse_twitter_header(cmpt)
    carousel = cmpt.find("g-scrolling-carousel")
    subs = carousel.find_all("g-inner-card") if carousel else []
    parsed_cards = [parse_twitter_card(sub, sub_rank + 1) for sub_rank, sub in enumerate(subs)]
    return [parsed_header] + parsed_cards


def parse_twitter_header(cmpt: bs4.element.Tag, sub_rank: int = 0) -> dict:
    parsed: dict[str, Any] = {"type": "twitter_cards", "sub_type": "header", "sub_rank": sub_rank}
    element_current = cmpt.find("g-link")
    element_legacy = cmpt.find("h3", {"class": "r"})
    if cmpt.find("h3"):
        if element_legacy:
            href = element_legacy.get("href", "")
            parsed["url"] = utils.url_unquote(str(href)) if href else None
            parsed["title"] = utils.get_text(element_legacy, "a")
        elif element_current:
            link = utils.get_link(element_current)
            parsed["url"] = utils.url_unquote(link) if link else None
            parsed["title"] = utils.get_text(element_current)
    elif element_current:
        parsed["url"] = utils.get_link(element_current)
        parsed["title"] = utils.get_text(element_current)
    parsed["cite"] = utils.get_text(cmpt, "cite")

    return parsed


def parse_twitter_card(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    parsed: dict[str, Any] = {"type": "twitter_cards", "sub_type": "card", "sub_rank": sub_rank}

    # Tweet account
    title = sub.find("g-link")
    parsed["title"] = utils.get_text(title, "a") if title else None

    # Bottom div containing details
    div = sub.find("div", {"class": "Brgz0"})
    if div:
        url = utils.get_link(div)
        parsed["url"] = utils.url_unquote(url) if url else None
        parsed["text"] = utils.get_text(div, "div", {"class": "xcQxib"})
        parsed["cite"] = utils.get_text(div, "div", {"class": "rmxqbe"})

    return parsed
