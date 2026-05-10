"""Parse an "Available on" component.

A carousel of thumbnail images linking to streaming providers / entertainment
options relevant to the query.
"""

import bs4

from ..utils import find_all_divs, get_link, get_text


def parse_available_on(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list:
    parsed: dict = {"type": "available_on", "sub_rank": sub_rank}
    parsed["title"] = get_text(cmpt, "span", {"class": "GzssTd"}) or get_text(
        cmpt, "span", {"class": "mgAbYb"}
    )
    parsed["details"] = None

    items: list[dict] = []

    # Legacy layout: tile divs inside the widget
    legacy_items = find_all_divs(cmpt, "div", {"class": "kno-fb-ctx"})
    items.extend(parse_available_on_item(i) for i in legacy_items)

    # Current layout: anchors with provider-name and cost sub-divs
    modern_widget = cmpt.find("div", {"class": "yTFeqb"})
    if modern_widget:
        for a in modern_widget.find_all("a", href=True):
            if a.find("div", {"class": "bclEt"}):
                items.append(parse_available_on_item_modern(a))

    if items:
        parsed["details"] = {"type": "hyperlinks", "items": items}
    return [parsed]


def parse_available_on_item(sub: bs4.element.Tag) -> dict:
    return {
        "url": get_link(sub),
        "text": get_text(sub, "div", {"class": "i3LlFf"}),
        "cost": get_text(sub, "div", {"class": "V8xno"}),
    }


def parse_available_on_item_modern(a: bs4.element.Tag) -> dict:
    return {
        "url": a.get("href"),
        "text": get_text(a, "div", {"class": "bclEt"}),
        "cost": get_text(a, "div", {"class": "rsj3fb"}),
    }
