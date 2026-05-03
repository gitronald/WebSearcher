"""Parse a "Map Results" component.

An embedded map result without an associated list of subcomponent results.
"""

import bs4

from .. import utils

_TITLE_SELECTORS = [
    ("div", {"class": "aiAXrc"}),
]


def parse_map_results(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list:
    return [
        {
            "type": "map_results",
            "sub_rank": sub_rank,
            "title": utils.get_text_by_selectors(cmpt, _TITLE_SELECTORS),
        }
    ]
