"""Parse a Flights component (Google Flights widget).

Renders as a section like "Flights to <destination>" followed by route cards
linking to google.com/travel/flights with origin labels (e.g. "From Casablanca").
"""

from .._slx import SoupNode as Node


def parse_flights(cmpt: Node) -> list:
    heading = cmpt.find(attrs={"role": "heading", "aria-level": "2"})
    title = heading.get_text(" ", strip=True) if heading else None
    items = []
    for a in cmpt.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(" ", strip=True)
        if href and href != "#" and text:
            items.append({"url": href, "text": text})
    parsed: dict = {
        "type": "flights",
        "sub_rank": 0,
        "title": title,
        "details": {"type": "hyperlinks", "items": items} if items else None,
    }
    return [parsed]
