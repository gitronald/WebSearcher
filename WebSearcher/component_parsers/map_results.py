"""Parse a "Map Results" component.

An embedded map result without an associated list of subcomponent results.
"""

from selectolax.parser import Node

from ..utils import Selector, get_text_by_selectors


def parse_map_results(cmpt: Node, sub_rank: int = 0) -> list:
    title_selectors = [
        Selector("div", {"class": "aiAXrc"}),
    ]
    return [
        {
            "type": "map_results",
            "sub_rank": sub_rank,
            "title": get_text_by_selectors(cmpt, title_selectors),
        }
    ]
