import bs4

from .. import utils
from ..utils import Selector

_TITLE_SELECTORS = [
    ("div", {"class": "zNWc4c"}),
    ("div", {"class": "qyp6xb"}),
]

_CITE_SELECTORS = [
    ("div", {"class": "LbKnXb"}),
    ("div", {"class": "VZGVuc"}),
]

_SUB_SELECTORS: list[Selector] = [
    Selector("div", {"class": "LJ7wUe"}),
    Selector("div", {"class": "JlqpRe"}),
    Selector("div", {"class": "EDblX"}),
]


def parse_discussions_and_forums(cmpt: bs4.element.Tag) -> list:
    """Parse a 'Discussions and forums' component"""
    for sel in _SUB_SELECTORS:
        subs = cmpt.find_all(sel.name, attrs=sel.attrs)
        if subs:
            return [parse_item(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    return []


def parse_item(cmpt: bs4.element.Tag, sub_rank: int = 0) -> dict:
    """Parse a 'Discussions and forums' subcomponent"""
    return {
        "type": "discussions_and_forums",
        "sub_type": None,
        "sub_rank": sub_rank,
        "title": get_title(cmpt),
        "url": get_url(cmpt),
        "cite": get_cite(cmpt),
    }


def get_title(sub):
    """Get title from selectors or heading div"""
    title = utils.get_text_by_selectors(sub, _TITLE_SELECTORS)
    if not title:
        title = utils.get_text(sub, "div", {"role": "heading"})
    return title


def get_cite(sub):
    """Get cite from selectors"""
    return utils.get_text_by_selectors(sub, _CITE_SELECTORS)


def get_url(sub):
    """Get URL from a subcomponent; try multiple, take first non-null"""
    url_list = [utils.get_link(sub, {"class": "v4kUNc"}), utils.get_link(sub)]
    url_list = [url for url in url_list if url]
    return url_list[0] if url_list else None
