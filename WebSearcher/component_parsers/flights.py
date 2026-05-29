"""Parse a Flights component (Google Flights widget).

Renders as a section like "Flights to <destination>" followed by route cards
linking to google.com/travel/flights with origin labels (e.g. "From Casablanca").
"""

from selectolax.parser import Node

from .._slx import get_text


def parse_flights(cmpt) -> list:
    node: Node = cmpt.raw
    heading = node.css_first('[role="heading"][aria-level="2"]')
    title = get_text(heading, " ", strip=True) if heading is not None else None
    items = []
    for a in node.css("a[href]"):
        href = a.attributes["href"]
        text = get_text(a, " ", strip=True)
        if href and href != "#" and text:
            items.append({"url": href, "text": text})
    parsed: dict = {
        "type": "flights",
        "sub_rank": 0,
        "title": title,
        "details": {"type": "hyperlinks", "items": items} if items else None,
    }
    return [parsed]
