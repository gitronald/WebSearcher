from .. import webutils
import bs4

TITLE_SELECTORS = [
    ('div', {'class': 'zNWc4c'}),
    ('div', {'class': 'qyp6xb'}),
]

CITE_SELECTORS = [
    ('div', {'class': 'LbKnXb'}),
    ('div', {'class': 'VZGVuc'}),
]


def parse_discussions_and_forums(cmpt:bs4.element.Tag) -> list:
    """Parse a 'Discussions and forums' component"""
    subs = cmpt.find_all("div", {"class":"LJ7wUe"})
    parsed_list = [parse_discussions_and_forums_item(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    return parsed_list

def parse_discussions_and_forums_item(cmpt:bs4.element.Tag, sub_rank:int = 0) -> dict:
    """Parse a 'Discussions and forums' subcomponent"""
    return {
        "type": "discussions_and_forums",
        "sub_type": None,
        "sub_rank": sub_rank,
        "title": webutils.get_text_by_selectors(cmpt, TITLE_SELECTORS),
        "url": get_url(cmpt),
        "cite": webutils.get_text_by_selectors(cmpt, CITE_SELECTORS)
    }

def get_url(sub):
    """Get URL from a subcomponent; try multiple, take first non-null"""
    url_list = [webutils.get_link(sub, {"class":"v4kUNc"}),
                webutils.get_link(sub)]
    url_list = [url for url in url_list if url]
    return url_list[0] if url_list else None

