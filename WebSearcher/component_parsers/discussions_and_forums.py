from .. import webutils
import bs4


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
        "title": get_title(cmpt),
        "url": get_url(cmpt),
        "cite": get_cite(cmpt)
    }

def get_url(sub):
    """Get URL from a subcomponent; try multiple, take first non-null"""
    url_list = [webutils.get_link(sub, {"class":"v4kUNc"}),
                webutils.get_link(sub)]
    url_list = [url for url in url_list if url]
    return url_list[0] if url_list else None

def get_title(sub):
    """Get title from a subcomponent; try multiple, take first non-null"""
    title_list = [webutils.get_text(sub, 'div', {'class':'zNWc4c'}),
                  webutils.get_text(sub, 'div', {'class':'qyp6xb'})]
    title_list = [title for title in title_list if title]
    return title_list[0] if title_list else None

def get_cite(sub):
    """Get cite from a subcomponent; try multiple, take first non-null"""
    cite_list = [webutils.get_text(sub, 'div', {'class':'LbKnXb'}),
                 webutils.get_text(sub, 'div', {'class':'VZGVuc'})]
    cite_list = [cite for cite in cite_list if cite]
    return cite_list[0] if cite_list else None
