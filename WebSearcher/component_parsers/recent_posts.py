"""Parse a "Recent posts" component.

Carousel similar to Top Stories and Perspectives.
"""

from .._slx import SoupNode as Node
from .top_stories import parse_top_stories


def parse_recent_posts(cmpt: Node) -> list:
    return parse_top_stories(cmpt, ctype="recent_posts")
