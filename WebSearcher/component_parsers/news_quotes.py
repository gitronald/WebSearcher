"""Parse a "Quotes in the News" component.

A horizontal carousel of news quotes, each pairing a pull-quote with the
underlying article title, source, and timestamp.
"""

import bs4


def parse_news_quotes(cmpt: bs4.element.Tag) -> list:
    subs = cmpt.find_all("g-inner-card")
    return [parse_news_quote(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_news_quote(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "news_quotes", "sub_rank": sub_rank}
    children: list = list(sub.children)

    if len(children) == 1 and isinstance(children[0], bs4.element.Tag):
        # Unfold nested div
        children = list(children[0].children)
    if len(children) == 2:
        quote, result = children
    else:  # Remove dummy div in middle
        quote, _, result = children

    if not isinstance(result, bs4.element.Tag):
        parsed["text"] = getattr(quote, "text", None)
        return parsed

    result_children: list = list(result.children)
    if len(result_children) == 2:
        title, meta = result_children
        if not isinstance(meta, bs4.element.Tag):
            return parsed
        cite, timestamp = meta.children
        parsed["title"] = title.text
        parsed["url"] = title["href"] if isinstance(title, bs4.element.Tag) else None
        parsed["cite"] = cite.text
        parsed["timestamp"] = timestamp.text
    else:
        title = result_children[1]
        cite = result_children[0]
        timestamp = result_children[2]  # dates are now relative vs absolute
        if isinstance(title, bs4.element.Tag) and title.div:
            parsed["title"] = title.div.text
            parsed["url"] = title["href"]
        if isinstance(cite, bs4.element.Tag) and cite.span:
            parsed["cite"] = cite.span.text
        if isinstance(timestamp, bs4.element.Tag) and timestamp.div:
            parsed["timestamp"] = timestamp.div.text

    parsed["text"] = quote.text

    return parsed
