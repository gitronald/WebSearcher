"""Parse a "Perspectives & opinions" component.

Same shape as Top Stories with a different heading. The heading text is
captured as the sub_type so downstream code can distinguish variants like
"what people are saying".
"""

import bs4

from .top_stories import parse_top_stories


def parse_perspectives(cmpt: bs4.element.Tag) -> list:
    header = cmpt.find(attrs={"aria-level": "2", "role": "heading"})
    if not header:
        header = cmpt.find("h2", {"role": "heading"})
    sub_type = header.text.strip().lower().replace(" ", "_") if header else None

    results = parse_top_stories(cmpt, ctype="perspectives")
    for result in results:
        result["sub_type"] = sub_type
    return results
