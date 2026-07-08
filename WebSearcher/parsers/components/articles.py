"""Parse an "Articles" module.

A ``g-section-with-header`` block titled "Articles" (an ``aria-level="2"``
heading span, typed by header text) listing article results, each a link to an
external publisher with a "<publisher> <headline>" caption. Rendered with a
thumbnail anchor plus a caption anchor to the same url, so dedupe by url.
"""

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text


def parse_articles(elem) -> list:
    node: Node = elem
    by_url: dict[str, str | None] = {}
    for anchor in node.css("a[href]"):
        href = anchor.attributes.get("href")
        # Skip the module's feedback affordance (href "#") and empty chips.
        if not href or href.startswith("#"):
            continue
        title = get_text(anchor, " ", strip=True)
        if href not in by_url or (title and not by_url[href]):
            by_url[href] = title
    return [
        {"type": "articles", "sub_rank": i, "title": t or None, "url": u}
        for i, (u, t) in enumerate(by_url.items())
    ]
