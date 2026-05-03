"""Parse a "Latest news" component.

Same shape as Top Stories, just a different heading.
"""

import bs4

from .top_stories import parse_top_stories


def parse_latest_from(cmpt: bs4.element.Tag) -> list:
    return parse_top_stories(cmpt, ctype="latest_from")
