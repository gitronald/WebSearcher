"""Parse a Google "supercat" discovery cluster (What to read / Courses / Explore stocks / ...).

A JS-hydrated recommendation carousel identified by a ``Supercat*ClusterTitle``
``data-attrid`` -- reused across content types, so a *books* cluster still carries
``SupercatRecipeClusterTitle``. Card links are ``#`` placeholders (JS-driven), so a
row carries a title (and, for book clusters, an author byline in ``text``) but no
url. The per-item markup is version-specific obfuscated classes; a content variant
whose item classes don't match yields no rows, but the component is still typed by
the structural classifier.
"""

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text
from ._common import mark_hidden_row


def parse_supercat_cluster(elem) -> list:
    node: Node = elem
    titles = node.css("div.sCqVCe")
    authors = node.css("div.kE4COc")
    parsed_list: list[dict] = []
    for i, title_el in enumerate(titles):
        title = get_text(title_el, strip=True)
        if not title:
            continue
        author_el = authors[i] if i < len(authors) else None
        row = {
            "type": "supercat_cluster",
            "sub_rank": i,
            "title": title,
            "url": None,
            "text": get_text(author_el, strip=True) if author_el is not None else None,
        }
        # The carousel shows a handful of cards and keeps the rest in a
        # ``display:none`` "More <items>" tail -- flag those visible=False.
        parsed_list.append(mark_hidden_row(row, title_el))
    return parsed_list
