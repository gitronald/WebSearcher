"""Parse a "Recent posts" component.

Carousel similar to Top Stories and Perspectives.
"""

from selectolax.parser import Node

from .top_stories import parse_top_stories


def parse_recent_posts(cmpt: Node) -> list:
    return parse_top_stories(cmpt, ctype="recent_posts")
