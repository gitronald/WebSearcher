"""Parse an "Explore places nearby" local places carousel.

A JS-hydrated horizontal carousel of nearby places (grocery stores, restaurants,
attractions, ...) titled "Explore places nearby" at an ``aria-level="2"`` heading
span. Each card is an ``aria-level="3"`` heading carrying the place name; the cards
are JS-driven (their anchors are ``#`` placeholders), so only the name is
extractable -- like the immersive products grid, rows carry a title but no url.
"""

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text


def parse_places_nearby(elem) -> list:
    node: Node = elem
    parsed_list: list[dict] = []
    for i, heading in enumerate(node.css('[aria-level="3"][role="heading"]')):
        name = get_text(heading, strip=True)
        if not name:
            continue
        parsed_list.append(
            {
                "type": "places_nearby",
                "sub_rank": i,
                "title": name,
                "url": None,
            }
        )
    return parsed_list
