"""Parse a "Quotes in the News" component.

A horizontal carousel of news quotes, each pairing a pull-quote with the
underlying article title, source, and timestamp.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text, is_element
from ._common import mark_timestamp_row


def parse_news_quotes(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    subs = list(node.css("g-inner-card"))
    return [parse_news_quote(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_news_quote(sub: Node, sub_rank: int = 0) -> dict[str, Any]:
    parsed: dict[str, Any] = {"type": "news_quotes", "sub_rank": sub_rank}
    # bs4 .children was text-inclusive; preserve that to match the original
    # element-counting destructure (1 / 2 / 3 children).
    children = list(sub.iter(include_text=True))

    if len(children) == 1 and is_element(children[0]):
        # Unfold nested div
        children = list(children[0].iter(include_text=True))
    if len(children) == 2:
        quote, result = children
    elif len(children) == 3:  # Remove dummy div in middle
        quote, _, result = children
    else:
        # Unrecognized card shape: keep the quote text rather than raising on
        # the destructure and losing every other card in the carousel.
        first = next((c for c in children if is_element(c)), None)
        parsed["text"] = (
            get_text(first) if first is not None else get_text(sub, " ", strip=True) or None
        )
        return parsed

    if not is_element(result):
        parsed["text"] = get_text(quote) if is_element(quote) else None
        return parsed

    result_children: list[Node] = list(result.iter(include_text=True))
    if len(result_children) == 2:
        title, meta = result_children
        parsed["title"] = get_text(title) if is_element(title) else None
        parsed["url"] = title.attrs.get("href") if is_element(title) else None
        if is_element(meta):
            meta_children = list(meta.iter(include_text=True))
            cite = meta_children[0] if meta_children else None
            timestamp = meta_children[1] if len(meta_children) >= 2 else None
            parsed["cite"] = get_text(cite) if is_element(cite) else None
            if is_element(timestamp):
                mark_timestamp_row(parsed, get_text(timestamp))
    elif len(result_children) >= 3:
        cite, title, timestamp = result_children[0], result_children[1], result_children[2]
        # bs4 ``.div`` / ``.span`` -> first descendant of that tag.
        if is_element(title):
            t_div = title.css_first("div")
            if t_div is not None:
                parsed["title"] = get_text(t_div)
            parsed["url"] = title.attrs.get("href")
        if is_element(cite):
            c_span = cite.css_first("span")
            if c_span is not None:
                parsed["cite"] = get_text(c_span)
        if is_element(timestamp):
            ts_div = timestamp.css_first("div")
            if ts_div is not None:
                mark_timestamp_row(parsed, get_text(ts_div))

    parsed["text"] = get_text(quote)

    return parsed
