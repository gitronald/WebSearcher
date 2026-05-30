"""Parse a "Scholarly articles" component.

Links to academic articles surfaced via Google Scholar.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text


def parse_scholarly_articles(elem) -> list:
    node: Node = elem
    rows = node.css("tr")
    if len(rows) < 2:
        return []
    subs = rows[1].css("div")
    return [parse_article(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_article(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "scholarly_articles", "sub_rank": sub_rank}
    parsed["title"] = get_text(sub)
    a = sub.css_first("a")
    if a is not None:
        parsed["url"] = a.attributes["href"]
        parsed["title"] = get_text(a)
        span = sub.css_first("span")
        parsed["cite"] = (get_text(span) or "").replace(" - ‎", "") if span is not None else None
    return parsed
