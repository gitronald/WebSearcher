"""Parse a promotional banner component.

A Google promo unit built around a ``<promo-throttler>`` element — currently the
"Save with deals on apparel, electronics, and more / Shop deals" shopping CTA.
It carries no organic result, so its value is the presence signal (shopping
intent). The CTA link is an internal ``/search`` query, kept verbatim.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text


def parse_promo(cmpt) -> list:
    node: Node = cmpt

    cta = node.css_first("a[href]")
    cta_url = cta.attributes["href"] if cta is not None else None

    cta_label = get_text(node.css_first("span.EfVwZc"), " ", strip=True) or None

    # Title is the promo description (full text minus the trailing CTA label).
    full = get_text(node, " ", strip=True)
    title = full
    if cta_label and full.endswith(cta_label):
        title = full[: -len(cta_label)].strip()

    return [
        {
            "type": "promo",
            "sub_type": "shopping",
            "sub_rank": 0,
            "title": title or None,
            "url": cta_url,
            "text": cta_label or None,
        }
    ]
