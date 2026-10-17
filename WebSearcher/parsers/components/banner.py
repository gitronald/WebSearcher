"""Parse a warning banner component.

A header row plus a list of clickable suggestions Google offers when a query
is flagged (e.g., misspellings, restricted topics).
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ._common import first_text


def parse_banner(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    parsed_list: list[dict[str, Any]] = [
        {
            "type": "banner",
            "sub_type": "header",
            "sub_rank": 0,
            "title": (first_text(node, ".v3jTId", sep="") or ""),
            "text": (first_text(node, ".Cy9gW", sep="") or ""),
        }
    ]

    for i, suggestion in enumerate(node.css(".TjBpC")):
        parsed_list.append(
            {
                "type": "banner",
                "sub_type": "suggestion",
                "sub_rank": i + 1,
                "title": (first_text(suggestion, ".AbPV3", sep="") or ""),
                "url": suggestion.attrs.get("href"),
            }
        )

    return parsed_list
