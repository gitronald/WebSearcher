"""Parse an "Available on" component.

A carousel of thumbnail images linking to streaming providers / entertainment
options relevant to the query.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text, has_text, is_hidden


def parse_available_on(elem, sub_rank: int = 0) -> list:
    node: Node = elem
    parsed: dict = {"type": "available_on", "sub_rank": sub_rank}
    parsed["title"] = get_text(node.css_first("span.GzssTd"), " ") or get_text(
        node.css_first("span.mgAbYb"), " "
    )
    parsed["details"] = None

    items: list[dict] = []

    # Legacy layout: tile divs inside the widget; skip the empty ones.
    for item in node.css("div.kno-fb-ctx"):
        if has_text(item):
            items.append(parse_available_on_item(item))

    # Current layout: anchors with provider-name and cost sub-divs
    modern_widget = node.css_first("div.yTFeqb")
    if modern_widget is not None:
        for a in modern_widget.css("a[href]"):
            if a.css_first("div.bclEt") is not None:
                items.append(parse_available_on_item_modern(a))

    if items:
        parsed["details"] = {"type": "hyperlinks", "items": items}
    return [parsed]


def parse_available_on_item(sub: Node) -> dict:
    a = sub.css_first("a")
    return {
        "url": a.attributes.get("href") if a is not None else None,
        "text": get_text(sub.css_first("div.i3LlFf"), " "),
        "cost": get_text(sub.css_first("div.V8xno"), " "),
        "visible": not is_hidden(sub),
    }


def parse_available_on_item_modern(a: Node) -> dict:
    return {
        "url": a.attributes.get("href"),
        "text": get_text(a.css_first("div.bclEt"), " "),
        "cost": get_text(a.css_first("div.rsj3fb"), " "),
        "visible": not is_hidden(a),
    }
