"""Parse shopping-refinement chip modules.

Two ``g-section-with-header`` modules whose title is an ``aria-level="2"``
heading span (typed by header text via ``ClassifyMainHeader``):

- ``refine_by`` - faceted product filters ("Refine by brand/color/...") whose
  chips link to a filtered ``/search`` query.
- ``shopping_ideas`` - product-category ideas ("Shopping ideas") whose chips
  link to a category ``/search`` query.

Both render as a flat list of query-chip anchors, so they share one parser.
"""

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text


def parse_refine_by(elem) -> list:
    return _parse_query_chips(elem, "refine_by")


def parse_shopping_ideas(elem) -> list:
    return _parse_query_chips(elem, "shopping_ideas")


def _parse_query_chips(elem, cmpt_type: str) -> list:
    node: Node = elem
    parsed_list: list[dict] = []
    for anchor in node.css("a[href]"):
        href = anchor.attributes.get("href")
        title = get_text(anchor, " ", strip=True)
        # Skip the module's feedback affordance and any empty chips.
        if not href or href.startswith("#") or not title:
            continue
        parsed_list.append(
            {
                "type": cmpt_type,
                "sub_rank": len(parsed_list),
                "title": title,
                "url": href,
            }
        )
    return parsed_list
