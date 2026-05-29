"""Parse a "Local news" component.

Same shape as Top Stories, just a different heading.
"""

from .top_stories import parse_top_stories


def parse_local_news(cmpt) -> list:
    return parse_top_stories(cmpt, ctype="local_news")
