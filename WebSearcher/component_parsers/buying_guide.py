"""Parse a "Buying guide" component.

A faceted accordion (e.g. "Buying guide: Graphics Tablets") of label -> question
rows (``div.ITWcLb`` carrying "label: question"). No links. One result row per
facet: ``title`` is the facet label, ``text`` is the question/value.
"""

import bs4


def parse_buying_guide(cmpt: bs4.element.Tag) -> list:
    out: list = []
    for row in cmpt.find_all("div", {"class": "ITWcLb"}):
        text = row.get_text(" ", strip=True)
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
