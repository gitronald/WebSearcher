"""Parse a "Recent posts" component.

Carousel similar to Top Stories and Perspectives.
"""

import bs4

from .top_stories import parse_top_stories


def parse_recent_posts(cmpt: bs4.element.Tag) -> list:
    return parse_top_stories(cmpt, ctype="recent_posts")
