"""Parse a "Local news" component.

Same shape as Top Stories, just a different heading.
"""

from .top_stories import parse_top_stories


def parse_local_news(elem) -> list:
    return parse_top_stories(elem, ctype="local_news")
