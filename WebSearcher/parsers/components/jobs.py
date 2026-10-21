"""Parse a Jobs component (Google for Jobs widget).

Renders as a section with a "Jobs" heading followed by individual job cards
(each with its own aria-level=3 heading: job title).
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text


def parse_jobs(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    heading = node.css_first('[role="heading"][aria-level="2"]')
    title = get_text(heading, " ", strip=True)
    items = [
        get_text(h, " ", strip=True) or "" for h in node.css('[role="heading"][aria-level="3"]')
    ]
    parsed: dict[str, Any] = {
        "type": "jobs",
        "sub_rank": 0,
        "title": title,
        "details": {"type": "text", "items": items} if items else None,
    }
    return [parsed]
