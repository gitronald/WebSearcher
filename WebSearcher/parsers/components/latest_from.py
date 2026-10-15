"""Parse a "Latest news" component.

Same shape as Top Stories, just a different heading.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from .top_stories import parse_top_stories


def parse_latest_from(elem: Node) -> list[dict[str, Any]]:
    return parse_top_stories(elem, ctype="latest_from")
