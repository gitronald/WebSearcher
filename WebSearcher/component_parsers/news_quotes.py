"""Parse a "Quotes in the News" component.

A horizontal carousel of news quotes, each pairing a pull-quote with the
underlying article title, source, and timestamp.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text


def parse_news_quotes(elem) -> list:
    node: Node = elem
    subs = list(node.css("g-inner-card"))
    return [parse_news_quote(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def _is_tag(n: Node | None) -> bool:
    return n is not None and bool(n.tag) and not n.tag.startswith("-")


def parse_news_quote(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "news_quotes", "sub_rank": sub_rank}
    # bs4 .children was text-inclusive; preserve that to match the original
    # element-counting destructure (1 / 2 / 3 children).
    children = list(sub.iter(include_text=True))

    if len(children) == 1 and _is_tag(children[0]):
        # Unfold nested div
        children = list(children[0].iter(include_text=True))
    if len(children) == 2:
        quote, result = children
    else:  # Remove dummy div in middle
        quote, _, result = children

    if not _is_tag(result):
        parsed["text"] = get_text(quote) if _is_tag(quote) else None
        return parsed

    result_children: list = list(result.iter(include_text=True))
    if len(result_children) == 2:
        title, meta = result_children
        if not _is_tag(meta):
            return parsed
        meta_children = list(meta.iter(include_text=True))
        cite, timestamp = meta_children[0], meta_children[1] if len(meta_children) >= 2 else None
        parsed["title"] = get_text(title) if _is_tag(title) else None
        parsed["url"] = title.attributes.get("href") if _is_tag(title) else None
        parsed["cite"] = get_text(cite) if _is_tag(cite) else None
        if timestamp is not None and _is_tag(timestamp):
            parsed["timestamp"] = get_text(timestamp)
    else:
        title = result_children[1]
        cite = result_children[0]
        timestamp = result_children[2]  # dates are now relative vs absolute
        # bs4 ``.div`` / ``.span`` -> first descendant of that tag.
        if _is_tag(title):
            t_div = title.css_first("div")
            if t_div is not None:
                parsed["title"] = get_text(t_div)
            parsed["url"] = title.attributes.get("href")
        if _is_tag(cite):
            c_span = cite.css_first("span")
            if c_span is not None:
                parsed["cite"] = get_text(c_span)
        if _is_tag(timestamp):
            ts_div = timestamp.css_first("div")
            if ts_div is not None:
                parsed["timestamp"] = get_text(ts_div)

    parsed["text"] = get_text(quote)

    return parsed
