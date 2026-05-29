"""Parse a "Perspectives & opinions" component.

Same shape as Top Stories with a different heading. The heading text is
captured as the sub_type so downstream code can distinguish variants like
"what people are saying".
"""

import bs4

from ..utils import slugify
from .top_stories import parse_top_stories


def parse_perspectives(cmpt: bs4.element.Tag) -> list:
    header = cmpt.find(attrs={"aria-level": "2", "role": "heading"})
    if not header:
        header = cmpt.find("h2", {"role": "heading"})
    heading_text = header.get_text(" ", strip=True) if header else None
    sub_type = slugify(heading_text.lower()) if heading_text else None

    results = parse_top_stories(cmpt, ctype="perspectives")
    for result in results:
        result["sub_type"] = sub_type
        # Preserve the raw component heading (the sub_type slug is lossy).
        if heading_text:
            details = result.get("details")
            if isinstance(details, dict):
                details["heading"] = heading_text
            else:
                result["details"] = {"heading": heading_text}
    return results
