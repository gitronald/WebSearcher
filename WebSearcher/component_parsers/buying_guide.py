"""Parse a "Buying guide" component.

A faceted accordion (e.g. "Buying guide: Graphics Tablets") of label -> question
rows (``div.ITWcLb`` carrying "label: question"). No links. One result row per
facet: ``title`` is the facet label, ``text`` is the question/value.
"""

from selectolax.parser import Node

from .._slx import get_text


def parse_buying_guide(cmpt) -> list:
    node: Node = cmpt.raw
    out: list = []
    for row in node.css("div.ITWcLb"):
        text = get_text(row, " ", strip=True)
        if not text:
            continue
        label, sep, value = text.partition(":")
        if sep:
            label, value = label.strip(), value.strip()
        else:
            label, value = None, text.strip()
        if not value:
            continue
        out.append(
            {
                "type": "buying_guide",
                "sub_rank": len(out),
                "title": label or None,
                "text": value or None,
            }
        )
    return out
