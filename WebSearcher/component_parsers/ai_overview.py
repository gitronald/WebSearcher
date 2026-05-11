"""Parse the AI Overview component.

Google's AI Overview is a synthesized answer panel that appears at or near the
top of a SERP. It comes in two layouts:

- ``flat`` — a single answer block (intro paragraph + optional bullet list)
- ``sectioned`` — an intro lede followed by N section subheadings (each with its
  own bullet list and optional inline links)

Both layouts share a "Sources" tray at the bottom that lists the publishers the
overview drew from.
"""

import bs4


def parse_ai_overview(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list[dict]:
    parsed: dict = {
        "type": "ai_overview",
        "sub_rank": sub_rank,
        "title": None,
        "url": None,
        "cite": None,
    }

    content = cmpt.find("div", {"class": "mZJni"})
    lede, sections = _extract_body(content) if content else ("", [])
    sources = _extract_sources(cmpt)

    if sections:
        parsed["sub_type"] = "sectioned"
        parsed["title"] = sections[0]["heading"]
    else:
        parsed["sub_type"] = "flat"

    parsed["text"] = lede or None

    details: dict = {"type": "ai_overview"}
    if sections:
        details["sections"] = sections
    if sources:
        details["sources"] = sources

    parsed["details"] = details if len(details) > 1 else None
    return [parsed]


_BODY_PARA_CLASS = "Y3BBE"
_BODY_HEADING_CLASS = "otQkpb"
_LIST_CLASSES = ("KsbFXc", "IaGLZe")


def _extract_body(content: bs4.element.Tag) -> tuple[str, list[dict]]:
    """Walk the content area and split into a lede + section list.

    The body is a flat document-order sequence of paragraph divs (``Y3BBE``),
    section heading divs (``otQkpb``, ``role=heading aria-level=3``), and
    bullet/ordered lists (``ul.KsbFXc`` / ``ol.IaGLZe``). Layout nests vary
    (sometimes wrapped in an extra div, sometimes flush with ``mZJni``), so
    we collect the elements via ``find_all`` and walk in document order.
    """
    elements = _collect_body_elements(content)
    if not elements:
        return "", []

    lede_parts: list[str] = []
    sections: list[dict] = []
    current: dict | None = None

    for elem in elements:
        if _is_section_heading(elem):
            current = {"heading": elem.get_text(" ", strip=True), "text": None, "hyperlinks": []}
            sections.append(current)
            continue

        text = elem.get_text(" ", strip=True)
        if not text:
            continue
        hyperlinks = _collect_inline_links(elem)

        if current is None:
            lede_parts.append(text)
        else:
            current["text"] = text if current["text"] is None else f"{current['text']} {text}"
            current["hyperlinks"].extend(hyperlinks)

    for sec in sections:
        if not sec["hyperlinks"]:
            del sec["hyperlinks"]

    return " ".join(lede_parts).strip(), sections


def _collect_body_elements(content: bs4.element.Tag) -> list[bs4.element.Tag]:
    """Collect paragraph/heading/list elements from the body in document order."""
    paragraphs = content.find_all("div", {"class": _BODY_PARA_CLASS})
    headings = content.find_all("div", {"class": _BODY_HEADING_CLASS})
    lists = [
        elem for cls in _LIST_CLASSES for elem in content.find_all(["ul", "ol"], {"class": cls})
    ]

    elements = list(paragraphs) + list(headings) + list(lists)
    # Deduplicate (Y3BBE divs can nest inside one another in some layouts)
    # and drop elements whose ancestor is already in the set.
    elements = _drop_nested_descendants(elements)
    return sorted(elements, key=_doc_position)


def _drop_nested_descendants(elements: list[bs4.element.Tag]) -> list[bs4.element.Tag]:
    elem_set = set(id(e) for e in elements)
    kept = []
    for e in elements:
        parent = e.parent
        skip = False
        while parent is not None:
            if id(parent) in elem_set:
                skip = True
                break
            parent = parent.parent
        if not skip:
            kept.append(e)
    return kept


def _doc_position(elem: bs4.element.Tag) -> tuple:
    """Crude document position via ancestor chain indices."""
    path = []
    node = elem
    while node.parent is not None:
        siblings = [c for c in node.parent.children if getattr(c, "name", None)]
        try:
            path.append(siblings.index(node))
        except ValueError:
            path.append(0)
        node = node.parent
    return tuple(reversed(path))


def _is_section_heading(elem: bs4.element.Tag) -> bool:
    if elem.name != "div":
        return False
    classes = elem.attrs.get("class") or []
    if _BODY_HEADING_CLASS in classes:
        return True
    return elem.attrs.get("role") == "heading" and elem.attrs.get("aria-level") == "3"


def _collect_inline_links(elem: bs4.element.Tag) -> list[dict]:
    """Collect anchors from inline body content (skips sources tray and #)."""
    links = []
    seen = set()
    for a in elem.find_all("a", href=True):
        href = str(a["href"])
        if href == "#" or href.startswith("/search?"):
            continue
        if a.find_parent("ul", {"class": "bTFeG"}):
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append({"url": href, "text": a.get_text(" ", strip=True)})
    return links


def _extract_sources(cmpt: bs4.element.Tag) -> list[dict]:
    """Pull the bottom "Sources" tray as a flat list of {url, text} entries.

    ``text`` is the publisher label (e.g. ``"CNN"``), pulled from the
    ``span.Z1JFYc`` element inside each source card.
    """
    sources_ul = cmpt.find("ul", {"class": "bTFeG"})
    if not sources_ul:
        return []
    sources = []
    seen = set()
    for li in sources_ul.find_all("li", {"class": "CyMdWb"}):
        a = li.find("a", href=True)
        if not a:
            continue
        href = str(a["href"])
        if href == "#" or href in seen:
            continue
        seen.add(href)
        publisher_span = li.find("span", {"class": "Z1JFYc"})
        publisher = publisher_span.get_text(" ", strip=True) if publisher_span else ""
        sources.append({"url": href, "text": publisher})
    return sources
