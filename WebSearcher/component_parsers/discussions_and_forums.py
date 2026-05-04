"""Parse a "Discussions and forums" component.

A list of forum/discussion threads (Reddit, Stack Overflow, etc.) with title,
source, and link. Each row has multiple known card layouts.
"""

import bs4

from .. import utils
from ..utils import Selector


def parse_discussions_and_forums(cmpt: bs4.element.Tag) -> list:
    sub_selectors: list[Selector] = [
        Selector("div", {"class": "LJ7wUe"}),
        Selector("div", {"class": "JlqpRe"}),
        Selector("div", {"class": "EDblX"}),
    ]
    for sel in sub_selectors:
        subs = cmpt.find_all(sel.name, attrs=sel.attrs)
        if subs:
            return [parse_item(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    return []


def parse_item(cmpt: bs4.element.Tag, sub_rank: int = 0) -> dict:
    return {
        "type": "discussions_and_forums",
        "sub_type": None,
        "sub_rank": sub_rank,
        "title": get_title(cmpt),
        "url": get_url(cmpt),
        "cite": get_cite(cmpt),
    }


def get_title(sub: bs4.element.Tag) -> str | None:
    title_selectors = [
        Selector("div", {"class": "zNWc4c"}),
        Selector("div", {"class": "qyp6xb"}),
    ]
    title = utils.get_text_by_selectors(sub, title_selectors)
    if not title:
        title = utils.get_text(sub, "div", {"role": "heading"})
    return title


def get_cite(sub: bs4.element.Tag) -> str | None:
    cite_selectors = [
        Selector("div", {"class": "LbKnXb"}),
        Selector("div", {"class": "VZGVuc"}),
    ]
    return utils.get_text_by_selectors(sub, cite_selectors)


def get_url(sub: bs4.element.Tag) -> str | None:
    # Try multiple, take first non-null
    url_list = [utils.get_link(sub, {"class": "v4kUNc"}), utils.get_link(sub)]
    url_list = [url for url in url_list if url]
    return url_list[0] if url_list else None
