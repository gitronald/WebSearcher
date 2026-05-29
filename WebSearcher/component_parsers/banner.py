"""Parse a warning banner component.

A header row plus a list of clickable suggestions Google offers when a query
is flagged (e.g., misspellings, restricted topics).
"""

from selectolax.parser import Node


def parse_banner(cmpt: Node) -> list:
    parsed_list: list[dict] = []

    parsed_list.append(
        {
            "type": "banner",
            "sub_type": "header",
            "sub_rank": 0,
            "title": _get_result_text(cmpt, ".v3jTId"),
            "text": _get_result_text(cmpt, ".Cy9gW"),
        }
    )

    for i, suggestion in enumerate(cmpt.select(".TjBpC")):
        parsed_list.append(
            {
                "type": "banner",
                "sub_type": "suggestion",
                "sub_rank": i + 1,
                "title": _get_result_text(suggestion, ".AbPV3"),
                "url": suggestion.get("href"),
            }
        )

    return parsed_list


def _get_result_text(cmpt: Node, selector: str) -> str:
    match = cmpt.select_one(selector)
    return match.get_text(strip=True) if match else ""
