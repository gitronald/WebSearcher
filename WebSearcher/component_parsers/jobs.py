"""Parse a Jobs component (Google for Jobs widget).

Renders as a section with a "Jobs" heading followed by individual job cards
(each with its own aria-level=3 heading: job title).
"""

from selectolax.parser import Node


def parse_jobs(cmpt: Node) -> list:
    heading = cmpt.find(attrs={"role": "heading", "aria-level": "2"})
    title = heading.get_text(" ", strip=True) if heading else None
    items = [
        h.get_text(" ", strip=True)
        for h in cmpt.find_all(attrs={"role": "heading", "aria-level": "3"})
    ]
    parsed: dict = {
        "type": "jobs",
        "sub_rank": 0,
        "title": title,
        "details": {"type": "text", "items": items} if items else None,
    }
    return [parsed]
