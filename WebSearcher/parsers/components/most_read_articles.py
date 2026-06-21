"""Parse a "Most-read articles" carousel.

An editorial carousel of article cards (one per publisher) shown on
commercial/research SERPs. Each real card is a ``role=listitem`` with an anchor
and an aria-level-3 heading; the carousel also holds empty placeholder slots,
which are skipped.
"""

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text


def parse_most_read_articles(elem) -> list:
    node: Node = elem
    out: list = []
    for li in node.css('[role="listitem"]'):
        a = li.css_first("a[href]")
        heading = li.css_first('[aria-level="3"]')
        if a is None or heading is None:
            continue
        title = get_text(heading, strip=True)
        if not title:
            continue
        out.append(
            {
                "type": "most_read_articles",
                "sub_rank": len(out),
                "title": title,
                "url": a.attributes["href"],
            }
        )
    return out
