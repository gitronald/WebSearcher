"""Parse a "Perspectives & opinions" component.

Same shape as Top Stories with a different heading. The heading text is
captured as the sub_type so downstream code can distinguish variants like
"what people are saying".
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text
from ..utils import slugify
from .top_stories import parse_top_stories


def parse_perspectives(elem) -> list:
    node: Node = elem
    header = node.css_first('[aria-level="2"][role="heading"]') or node.css_first(
        'h2[role="heading"]'
    )
    heading_text = get_text(header, " ", strip=True) if header is not None else None
    sub_type = slugify(heading_text.lower()) if heading_text else None

    results = parse_top_stories(node, ctype="perspectives")
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
