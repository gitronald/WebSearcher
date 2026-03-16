from .top_stories import parse_top_stories


def parse_perspectives(cmpt):
    """Parse a "Perspectives & opinions" component

    These components are the same as Top Stories, but have a different heading.

    Args:
        cmpt (bs4 object): A latest from component

    Returns:
        dict : parsed result
    """
    # Extract header text as sub_type (e.g. "What people are saying" -> "what_people_are_saying")
    header = cmpt.find(attrs={"aria-level": "2", "role": "heading"})
    if not header:
        header = cmpt.find("h2", {"role": "heading"})
    sub_type = header.text.strip().lower().replace(" ", "_") if header else None

    results = parse_top_stories(cmpt, ctype="perspectives")
    for result in results:
        result["sub_type"] = sub_type
    return results
