"""Parse a promotional banner component.

A Google promo unit built around a ``<promo-throttler>`` element — currently the
"Save with deals on apparel, electronics, and more / Shop deals" shopping CTA.
It carries no organic result, so its value is the presence signal (shopping
intent). The CTA link is an internal ``/search`` query, kept verbatim.
"""

from selectolax.parser import Node


def parse_promo(cmpt: Node) -> list:
    cta = cmpt.find("a", href=True)
    cta_url = cta["href"] if cta else None

    cta_label_el = cmpt.find("span", {"class": "EfVwZc"})
    cta_label = cta_label_el.get_text(" ", strip=True) if cta_label_el else None

    # Title is the promo description (full text minus the trailing CTA label).
    full = cmpt.get_text(" ", strip=True)
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
