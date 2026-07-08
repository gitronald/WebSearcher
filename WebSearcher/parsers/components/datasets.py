"""Parse a "Datasets" results module.

Google's dataset-search unit: a ``g-section-with-header`` block titled
"Datasets" (an ``aria-level="2"`` heading span) listing dataset results, each an
``h3`` title wrapped in an anchor to the source (Statista, data.gov, ...). The
title span is not an ``h2``/``h3``, so the module is typed by header text via
``ClassifyMainHeader`` (``header_texts={2: ("Datasets",)}``).
"""

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text


def parse_datasets(elem) -> list:
    node: Node = elem
    parsed_list: list[dict] = []
    for i, h3 in enumerate(node.css("h3")):
        url = None
        anchor = h3
        for _ in range(4):
            anchor = anchor.parent
            if anchor is None:
                break
            if anchor.tag == "a" and anchor.attributes.get("href"):
                url = anchor.attributes.get("href")
                break
        parsed_list.append(
            {
                "type": "datasets",
                "sub_rank": i,
                "title": get_text(h3, strip=True) or None,
                "url": url,
            }
        )
    return parsed_list
