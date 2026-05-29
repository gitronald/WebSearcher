"""Parse a "Quotes in the News" component.

A horizontal carousel of news quotes, each pairing a pull-quote with the
underlying article title, source, and timestamp.
"""

from selectolax.parser import Node

from .._slx import is_tag


def parse_news_quotes(cmpt: Node) -> list:
    subs = cmpt.find_all("g-inner-card")
    return [parse_news_quote(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_news_quote(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "news_quotes", "sub_rank": sub_rank}
    children: list = list(sub.children)

    if len(children) == 1 and is_tag(children[0]):
        # Unfold nested div
        children = list(children[0].children)
    if len(children) == 2:
        quote, result = children
    else:  # Remove dummy div in middle
        quote, _, result = children

    if not is_tag(result):
        parsed["text"] = getattr(quote, "text", None)
        return parsed

    result_children: list = list(result.children)
    if len(result_children) == 2:
        title, meta = result_children
        if not is_tag(meta):
            return parsed
        cite, timestamp = meta.children
        parsed["title"] = title.text
        parsed["url"] = title["href"] if is_tag(title) else None
        parsed["cite"] = cite.text
        parsed["timestamp"] = timestamp.text
    else:
        title = result_children[1]
        cite = result_children[0]
        timestamp = result_children[2]  # dates are now relative vs absolute
        if is_tag(title) and title.div:
            parsed["title"] = title.div.text
            parsed["url"] = title["href"]
        if is_tag(cite) and cite.span:
            parsed["cite"] = cite.span.text
        if is_tag(timestamp) and timestamp.div:
            parsed["timestamp"] = timestamp.div.text

    parsed["text"] = quote.text

    return parsed
