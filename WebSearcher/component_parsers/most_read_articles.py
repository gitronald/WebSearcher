"""Parse a "Most-read articles" carousel.

An editorial carousel of article cards (one per publisher) shown on
commercial/research SERPs. Each real card is a ``role=listitem`` with an anchor
and an aria-level-3 heading; the carousel also holds empty placeholder slots,
which are skipped.
"""

from .._slx import SoupNode as Node


def parse_most_read_articles(cmpt: Node) -> list:
    out: list = []
    for li in cmpt.find_all(attrs={"role": "listitem"}):
        a = li.find("a", href=True)
        heading = li.find(attrs={"aria-level": "3"})
        if a is None or heading is None:
            continue
        title = heading.get_text(strip=True)
        if not title:
            continue
        out.append(
            {
                "type": "most_read_articles",
                "sub_rank": len(out),
                "title": title,
                "url": a["href"],
            }
        )
    return out
