"""Parse an "Available on" component.

A carousel of thumbnail images linking to streaming providers / entertainment
options relevant to the query.
"""

import bs4

from ..utils import find_all_divs, get_link, get_text


def parse_available_on(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list:
    parsed: dict = {"type": "available_on", "sub_rank": sub_rank}
    parsed["title"] = get_text(cmpt, "span", {"class": "GzssTd"})
    parsed["details"] = None

    items = find_all_divs(cmpt, "div", {"class": "kno-fb-ctx"})
    if items:
        parsed["details"] = {
            "type": "providers",
            "items": [parse_available_on_item(i) for i in items],
        }
    return [parsed]


def parse_available_on_item(sub: bs4.element.Tag) -> dict:
    return {
        "title": get_text(sub, "div", {"class": "i3LlFf"}),
        "url": get_link(sub),
        "cost": get_text(sub, "div", {"class": "V8xno"}),
    }
