"""Parse a Flights component (Google Flights widget).

Renders as a section like "Flights to <destination>" followed by route cards
linking to google.com/travel/flights with origin labels (e.g. "From Casablanca").
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text


def parse_flights(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    # The flight-status widget uses a bare <h2> with no role="heading".
    heading = node.css_first('[role="heading"][aria-level="2"]') or node.css_first("h2")
    title = get_text(heading, " ", strip=True)
    items = []
    for a in node.css("a[href]"):
        href = a.attrs["href"]
        text = get_text(a, " ", strip=True)
        if href and href != "#" and text:
            items.append({"url": href, "text": text})
    parsed: dict[str, Any] = {
        "type": "flights",
        "sub_rank": 0,
        "title": title,
        "details": {"type": "hyperlinks", "items": items} if items else None,
    }
    return [parsed]
