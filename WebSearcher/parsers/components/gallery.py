"""Parse a Google discovery "gallery" cluster (What to read / Courses / Explore stocks / ...).

A JS-hydrated recommendation carousel identified by a ``Supercat*ClusterTitle``
``data-attrid`` -- reused across content types, so a *books* cluster still carries
``SupercatRecipeClusterTitle``. The parse emits:

- a **header** row (``sub_type="header"``): the cluster heading as ``title`` and the
  category-filter chips ("Principles of Islamic jurisprudence", "Law", ...) joined
  into ``text``;
- one **item** row per card: title (+ author byline in ``text``). Card links are ``#``
  placeholders (JS-driven), so items carry no url; items past the initial few sit in a
  ``display:none`` "More <items>" tail and are flagged ``visible=False``.

Per-item / chip markup is version-specific obfuscated classes; a content variant whose
classes don't match still types via the structural classifier but yields fewer rows.
"""

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text
from ._common import mark_hidden_row

_TEXT_SEP = "<|>"


def parse_gallery(elem) -> list:
    node: Node = elem
    parsed_list: list[dict] = []

    # Header row: cluster heading + joined category-filter chips.
    heading = node.css_first('[aria-level="2"][role="heading"]')
    heading_text = get_text(heading, strip=True) if heading is not None else None
    chips = [t for t in (get_text(b, strip=True) for b in node.css('[role="button"].alvTwe')) if t]
    if heading_text or chips:
        parsed_list.append(
            {
                "type": "gallery",
                "sub_type": "header",
                "sub_rank": 0,
                "title": heading_text,
                "url": None,
                "text": _TEXT_SEP.join(chips) or None,
            }
        )

    # Item rows: one per card (title + author byline).
    titles = node.css("div.sCqVCe")
    authors = node.css("div.kE4COc")
    for i, title_el in enumerate(titles):
        title = get_text(title_el, strip=True)
        if not title:
            continue
        author_el = authors[i] if i < len(authors) else None
        row = {
            "type": "gallery",
            "sub_type": "card",
            "sub_rank": len(parsed_list),
            "title": title,
            "url": None,
            "text": get_text(author_el, strip=True) if author_el is not None else None,
        }
        parsed_list.append(mark_hidden_row(row, title_el))
    return parsed_list
