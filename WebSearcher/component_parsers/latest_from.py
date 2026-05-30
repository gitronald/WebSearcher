"""Parse a "Latest news" component.

Same shape as Top Stories, just a different heading.
"""

from .top_stories import parse_top_stories


def parse_latest_from(elem) -> list:
    return parse_top_stories(elem, ctype="latest_from")
