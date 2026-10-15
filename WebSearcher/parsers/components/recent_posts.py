"""Parse a "Recent posts" component.

Carousel similar to Top Stories and Perspectives.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from .top_stories import parse_top_stories


def parse_recent_posts(elem: Node) -> list[dict[str, Any]]:
    return parse_top_stories(elem, ctype="recent_posts")
