"""Parse an "Available on" component.

A carousel of thumbnail images linking to streaming providers / entertainment
options relevant to the query.
"""

import bs4


def parse_available_on(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list:
    parsed: dict = {"type": "available_on", "sub_rank": sub_rank}
    title = cmpt.find("span", {"class": "GzssTd"})
    parsed["title"] = title.text if title else None

    items = []
    for o in cmpt.find_all("div", {"class": "kno-fb-ctx"}):
        items.append(parse_available_on_item(o))
    parsed["details"] = {"type": "providers", "items": items} if items else None
    return [parsed]


def parse_available_on_item(sub: bs4.element.Tag) -> dict:
    title = sub.find("div", {"class": "i3LlFf"})
    a = sub.find("a")
    cost = sub.find("div", {"class": "V8xno"})
    return {
        "title": title.text if title else None,
        "url": a["href"] if a else None,
        "cost": cost.text if cost else None,
    }
