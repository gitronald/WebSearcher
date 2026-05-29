"""Parse a "Scholarly articles" component.

Links to academic articles surfaced via Google Scholar.
"""

from selectolax.parser import Node


def parse_scholarly_articles(cmpt: Node) -> list:
    subs = cmpt.find_all("tr")[1].find_all("div")
    return [parse_article(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def parse_article(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {"type": "scholarly_articles", "sub_rank": sub_rank}
    parsed["title"] = sub.text
    a = sub.find("a")
    if a:
        parsed["url"] = a.attrs["href"]
        parsed["title"] = a.text
        span = sub.find("span")
        parsed["cite"] = span.text.replace(" - \u200e", "") if span else None
    return parsed
