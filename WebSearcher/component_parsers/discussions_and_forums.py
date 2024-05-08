from .. import webutils
from ..models import BaseResult
import bs4

def parse_discussions_and_forums(cmpt:bs4.element.Tag) -> list:
    """Parse a 'Discussions and forums' component"""
    subs = cmpt.find_all("div", {"class":"LJ7wUe"})
    parsed_list = [parse_discussions_and_forums_item(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    return parsed_list


def parse_discussions_and_forums_item(cmpt:bs4.element.Tag, sub_rank:int = 0) -> dict:
    """Parse a 'Discussions and forums' subcomponent"""
    parsed = {"type": "discussions_and_forums", 
              "sub_type": None, 
              "sub_rank": sub_rank}
    parsed['title'] = webutils.get_text(cmpt, 'div', {'class':'zNWc4c'})
    parsed['url'] = webutils.get_link(cmpt, {"class":"v4kUNc"})
    parsed['cite'] = webutils.get_text(cmpt, 'div', {'class':'LbKnXb'})
    validated = BaseResult(**parsed)
    return validated.model_dump()