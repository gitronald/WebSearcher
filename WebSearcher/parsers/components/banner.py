"""Parse a warning banner component.

A header row plus a list of clickable suggestions Google offers when a query
is flagged (e.g., misspellings, restricted topics).
"""

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text


def parse_banner(elem) -> list:
    node: Node = elem
    parsed_list: list[dict] = [
        {
            "type": "banner",
            "sub_type": "header",
            "sub_rank": 0,
            "title": _get_result_text(node, ".v3jTId"),
            "text": _get_result_text(node, ".Cy9gW"),
        }
    ]

    for i, suggestion in enumerate(node.css(".TjBpC")):
        parsed_list.append(
            {
                "type": "banner",
                "sub_type": "suggestion",
                "sub_rank": i + 1,
                "title": _get_result_text(suggestion, ".AbPV3"),
                "url": suggestion.attributes.get("href"),
            }
        )

    return parsed_list


def _get_result_text(node: Node, selector: str) -> str:
    """Find first descendant matching ``selector`` and return its stripped text.
    Returns ``""`` (not ``None``) when missing, matching the original behavior."""
    return get_text(node.css_first(selector), strip=True) or ""
