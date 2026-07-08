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
        parsed_list.append(
            {
                "type": "supercat_cluster",
                "sub_rank": i,
                "title": title,
                "url": None,
                "text": get_text(author_el, strip=True) if author_el is not None else None,
            }
        )
    return parsed_list
