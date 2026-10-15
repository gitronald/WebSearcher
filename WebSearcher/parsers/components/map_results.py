"""Parse a "Map Results" component.

An embedded map result without an associated list of subcomponent results.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text


def parse_map_results(elem: Node, sub_rank: int = 0) -> list[dict[str, Any]]:
    node: Node = elem
    return [
        {
            "type": "map_results",
            "sub_rank": sub_rank,
            "title": get_text(node.css_first("div.aiAXrc"), " ") or None,
        }
    ]
