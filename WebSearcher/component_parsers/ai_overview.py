"""Parse the AI Overview component.

Google's AI Overview is a synthesized answer panel that appears at or near the
top of a SERP. It comes in two layouts:

- ``flat`` — a single answer block (intro paragraph + optional bullet list)
- ``sectioned`` — an intro lede followed by N section subheadings (each with its
  own bullet list and optional inline links)
- ``unavailable`` — the component was detected but Google declined to synthesize
  an overview ("An AI Overview is not available for this search"). No body or
  sources; recorded explicitly so a decline is distinguishable from a parser
  miss (which stays ``flat`` with empty output).

Both layouts share a "Sources" tray at the bottom that lists the publishers the
overview drew from. Per-section ``button.rBl3me`` widgets carry citation
metadata sourced from JSON payloads that Google ships in HTML comments / script
pushes alongside the rendered markup. See ``_ai_overview_payloads`` for the
extraction details.

Historical (2024-era) SGE captures use a different DOM with none of the current
classes: the body container ``div.mZJni`` is absent, paragraphs are
``div.rPeykc``, section headings are a ``span[role=heading]`` nested inside a
``rPeykc`` div, content bullets are plain ``ul``/``ol`` lists, and the sources
tray is ``li.LLtSOc`` cards (anchor ``a.KEVENd``, title in the anchor's
``aria-label`` / ``div.mNme1d``, snippet in ``span.gxZfx``). When the current
body container is missing we fall back to the legacy extractors below; those
captures predate the JSON citation payloads, so legacy sources come straight
from the rendered tray. "Can't generate an AI overview right now" failures carry
none of these markers and correctly yield empty output.
"""

from __future__ import annotations

import bs4

from ._ai_overview_payloads import extract_payloads


def parse_ai_overview(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list[dict]:
    parsed: dict = {
        "type": "ai_overview",
        "sub_rank": sub_rank,
        "title": None,
        "url": None,
        "cite": None,
    }

    content = cmpt.find("div", {"class": "mZJni"})
    if content is not None:
        # Payload extraction serializes the whole document; only the current
        # DOM ships these JSON citation payloads, so skip it for legacy SERPs.
        payloads = extract_payloads(_root_html(cmpt))
        type_a_by_src_id = _index_type_a_by_src_id(payloads)
        lede, lede_citations, sections = _extract_body(content, payloads)
        sources = _extract_sources(cmpt, type_a_by_src_id)
    else:
        # Legacy SGE (2024) markup: the current-DOM body container is absent.
        lede, lede_citations, sections = _extract_body_legacy(cmpt)
        sources = _extract_sources_legacy(cmpt)

    parsed["sub_type"] = "sectioned" if sections else "flat"
    parsed["text"] = lede or None

    details: dict = {"type": "ai_overview"}
    if sections:
        details["sections"] = sections
    if lede_citations:
        details["citations"] = lede_citations
    if sources:
        details["sources"] = sources

    parsed["details"] = details if len(details) > 1 else None

    # Distinguish a genuine "Google declined to generate" panel from a parser
    # miss: both otherwise yield empty output. The decline message is shipped
    # (hidden) on every AI-overview page, so it is only meaningful when no
    # content was extracted.
    if parsed["text"] is None and parsed["details"] is None and _is_unavailable(cmpt):
        parsed["sub_type"] = "unavailable"

    return [parsed]


_BODY_PARA_CLASS = "Y3BBE"
_BODY_HEADING_CLASS = "otQkpb"
_LIST_CLASSES = ("KsbFXc", "IaGLZe")

# Messages shown when Google declines to synthesize an overview. Both are
# present (hidden) on every AI-overview page, so they only carry meaning when
# no overview content was extracted. The second is apostrophe-agnostic.
_UNAVAILABLE_MARKERS = (
    "An AI Overview is not available for this search",
    "generate an AI overview right now",
)


def _is_unavailable(cmpt: bs4.element.Tag) -> bool:
    text = cmpt.get_text(" ", strip=True)
    return any(marker in text for marker in _UNAVAILABLE_MARKERS)


def _root_html(cmpt: bs4.element.Tag) -> str:
    """Serialize the document root (or the cmpt's highest ancestor) to HTML.

    The ``lDPB.push`` fallback payload form lives in script tags outside the
    AI overview cmpt, so we serialize the full document to catch all three
    payload delivery forms in one pass.
    """
    node = cmpt
    while node.parent is not None:
        node = node.parent
    return str(node)


def _extract_body(
    content: bs4.element.Tag, payloads: dict[str, dict]
) -> tuple[str, list[dict], list[dict]]:
    """Walk the content area and split into lede + lede citations + sections.

    The body is a flat document-order sequence of paragraph divs (``Y3BBE``),
    section heading divs (``otQkpb``, ``role=heading aria-level=3``), and
    bullet/ordered lists (``ul.KsbFXc`` / ``ol.IaGLZe``). Layout nests vary
    (sometimes wrapped in an extra div, sometimes flush with ``mZJni``), so
    we collect the elements via ``find_all`` and walk in document order.

    Citation buttons (``button.rBl3me``) inside each element are decomposed
    before text extraction (their visible text "Publisher +N" would otherwise
    leak into the paragraph) and recorded as a ``citations`` list per section
    (or attached to the lede if they precede any heading).
    """
    elements = _collect_body_elements(content)
    if not elements:
        return "", [], []

    lede_parts: list[str] = []
    lede_citations: list[dict] = []
    sections: list[dict] = []
    current: dict | None = None

    for elem in elements:
        button_citations = _extract_button_citations(elem, payloads)
        # Strip buttons before text extraction so the "Publisher +N" label
        # does not leak into the section text.
        for button in elem.find_all("button", {"class": "rBl3me"}):
            button.decompose()

        if _is_section_heading(elem):
            current = {
                "heading": elem.get_text(" ", strip=True),
                "text": None,
                "hyperlinks": [],
                "citations": [],
            }
            sections.append(current)
            if button_citations:
                current["citations"].extend(button_citations)
            continue

        text = elem.get_text(" ", strip=True)
        hyperlinks = _collect_inline_links(elem)

        if current is None:
            if text:
                lede_parts.append(text)
            if button_citations:
                lede_citations.extend(button_citations)
        else:
            if text:
                current["text"] = text if current["text"] is None else f"{current['text']} {text}"
            current["hyperlinks"].extend(hyperlinks)
            if button_citations:
                current["citations"].extend(button_citations)

    for sec in sections:
        if not sec["hyperlinks"]:
            del sec["hyperlinks"]
        if not sec["citations"]:
            del sec["citations"]

    return " ".join(lede_parts).strip(), lede_citations, sections


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
    elem_set = set(elements)
    kept = []
    for e in elements:
        parent = e.parent
        skip = False
        while parent is not None:
            if parent in elem_set:
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


def _extract_button_citations(elem: bs4.element.Tag, payloads: dict[str, dict]) -> list[dict]:
    """Build citation dicts for ``button.rBl3me`` widgets within ``elem``.

    For each button we record:

    - ``publisher`` — the visible publisher label (``span.QnvSdb``) or, for
      unattributed buttons, ``None``.
    - ``additional_count`` — the ``+N`` overflow count from ``span.IjM6od``,
      zero when absent.
    - ``source_ids`` — the list of ``data-src-id`` values from the button's
      Type-A payloads, in payload order. May be shorter than the header
      ``total`` when some cited sources have no resolved ``data-src-id``.

    Unattributed buttons with no payload data are dropped silently
    (Google's "View related links" panel-open widgets).
    """
    citations: list[dict] = []
    for button in elem.find_all("button", {"class": "rBl3me"}):
        uuid_raw = button.get("data-icl-uuid")
        if not uuid_raw:
            continue
        uuid = str(uuid_raw)
        publisher = _button_publisher(button)
        additional_count = _button_additional_count(button)
        payload = payloads.get(uuid, {})
        source_ids = [
            entry["source_id"] for entry in payload.get("type_a", []) if entry.get("source_id")
        ]
        # Unattributed panel-open buttons with no cited sources carry no
        # useful information — drop them silently.
        if publisher is None and not source_ids:
            continue
        citations.append(
            {
                "publisher": publisher,
                "additional_count": additional_count,
                "source_ids": source_ids,
            }
        )
    return citations


def _button_publisher(button: bs4.element.Tag) -> str | None:
    """Pull the publisher label from ``span.iFMVXd`` inside a ``rBl3me`` button.

    Attributed buttons render ``Publisher +N`` with the publisher in
    ``iFMVXd`` and the overflow count in a sibling ``IjM6od``. Unattributed
    panel-open buttons have neither.
    """
    span = button.find("span", {"class": "iFMVXd"})
    if span is None:
        return None
    text = span.get_text(" ", strip=True)
    return text or None


def _button_additional_count(button: bs4.element.Tag) -> int:
    span = button.find("span", {"class": "IjM6od"})
    if span is None:
        return 0
    text = span.get_text(" ", strip=True).lstrip("+").strip()
    try:
        return int(text)
    except ValueError:
        return 0


def _index_type_a_by_src_id(payloads: dict[str, dict]) -> dict[str, dict]:
    """Flatten all Type-A payloads into a ``data-src-id -> entry`` map.

    Any UUID may carry an entry for a given source. We keep the first
    occurrence per ``source_id`` (payload iteration order).
    """
    out: dict[str, dict] = {}
    for bucket in payloads.values():
        for entry in bucket.get("type_a", []):
            src_id = entry.get("source_id")
            if not src_id or src_id in out:
                continue
            out[src_id] = entry
    return out


def _extract_sources(cmpt: bs4.element.Tag, type_a_by_src_id: dict[str, dict]) -> list[dict]:
    """Build the sources list in tray (rank) order.

    Walks ``ul.bTFeG > li.CyMdWb`` in document order. For each, reads the
    ``data-src-id`` from the inner card and pulls ``title``/``snippet``/
    ``favicon``/``publisher`` from the matching Type-A payload. Falls back to
    the tray's ``span.Z1JFYc`` for ``publisher`` when the payload's publisher
    slot is empty.

    The tray order is Google's curated ranking and must not be reordered.
    """
    sources_ul = cmpt.find("ul", {"class": "bTFeG"})
    if not sources_ul:
        return []
    sources = []
    seen_src_ids: set[str] = set()
    for li in sources_ul.find_all("li", {"class": "CyMdWb"}):
        src_id_node = li.find(attrs={"data-src-id": True})
        src_id_raw = src_id_node.get("data-src-id") if src_id_node else None
        src_id = str(src_id_raw) if src_id_raw else None
        a = li.find("a", href=True)
        href = str(a["href"]) if a else None
        if not href or href == "#":
            continue
        if src_id and src_id in seen_src_ids:
            continue
        if src_id:
            seen_src_ids.add(src_id)

        payload = type_a_by_src_id.get(src_id, {}) if src_id else {}
        publisher = payload.get("publisher") or _tray_publisher(li) or ""
        sources.append(
            {
                "source_id": src_id,
                "url": payload.get("url") or href,
                "title": payload.get("title"),
                "snippet": payload.get("snippet"),
                "publisher": publisher,
                "favicon": payload.get("favicon"),
            }
        )
    return sources


def _tray_publisher(li: bs4.element.Tag) -> str | None:
    span = li.find("span", {"class": "Z1JFYc"})
    if span is None:
        return None
    text = span.get_text(" ", strip=True)
    return text or None


# --- Legacy SGE (2024) markup ---------------------------------------------

_LEGACY_PARA_CLASS = "rPeykc"
_LEGACY_SOURCE_LI_CLASS = "LLtSOc"
_SOURCES_UL_CLASS = "zVKf0d"


def _extract_body_legacy(
    content: bs4.element.Tag,
) -> tuple[str, list[dict], list[dict]]:
    """Walk the 2024 SGE body into lede + sections (no payload citations).

    The body is a document-order mix of ``div.rPeykc`` blocks and plain
    ``ul``/``ol`` content lists. A ``rPeykc`` whose subtree holds a
    ``[role=heading]`` (other than the ``Fzsovc`` "AI Overview" label) starts a
    new section; other ``rPeykc`` blocks and the content lists carry text.
    The sources tray (``ul.zVKf0d`` / ``li.LLtSOc``) is excluded here.
    """
    paragraphs = content.find_all("div", {"class": _LEGACY_PARA_CLASS})
    lists = [
        lst
        for lst in content.find_all(["ul", "ol"])
        if _SOURCES_UL_CLASS not in (lst.attrs.get("class") or [])
        and lst.find_parent("li", {"class": _LEGACY_SOURCE_LI_CLASS}) is None
    ]
    elements = _drop_nested_descendants(list(paragraphs) + list(lists))
    elements = sorted(elements, key=_doc_position)
    if not elements:
        return "", [], []

    lede_parts: list[str] = []
    sections: list[dict] = []
    current: dict | None = None

    for elem in elements:
        heading = _legacy_section_heading(elem)
        if heading is not None:
            current = {"heading": heading, "text": None, "hyperlinks": []}
            sections.append(current)
            continue

        text = elem.get_text(" ", strip=True)
        hyperlinks = _collect_inline_links(elem)
        if current is None:
            if text:
                lede_parts.append(text)
        else:
            if text:
                current["text"] = text if current["text"] is None else f"{current['text']} {text}"
            current["hyperlinks"].extend(hyperlinks)

    for sec in sections:
        if not sec["hyperlinks"]:
            del sec["hyperlinks"]

    return " ".join(lede_parts).strip(), [], sections


def _legacy_section_heading(elem: bs4.element.Tag) -> str | None:
    """Return the section-heading text if ``elem`` wraps a SGE section heading.

    Section headings are a ``[role=heading]`` node nested in a ``rPeykc`` div.
    The ``Fzsovc`` "AI Overview" component label is also a role-heading and must
    not be treated as a section.
    """
    heading = elem.find(attrs={"role": "heading"})
    if heading is None:
        return None
    if "Fzsovc" in (heading.attrs.get("class") or []):
        return None
    text = heading.get_text(" ", strip=True)
    return text or None


def _extract_sources_legacy(cmpt: bs4.element.Tag) -> list[dict]:
    """Build the sources list from the legacy ``li.LLtSOc`` tray cards.

    These captures predate the JSON citation payloads, so each source is read
    straight from the rendered card: ``a.KEVENd`` href + ``aria-label`` title
    (``div.mNme1d`` fallback), publisher label ``div.R8BTeb``, snippet
    ``span.gxZfx``. ``source_id`` and ``favicon`` (a large base64 data URI here)
    are left ``None``. 2024 SGE renders at most ~3 sources inline (the rest were
    JS-loaded and are absent from the saved HTML); tray order is Google's curated
    ranking and is preserved.
    """
    sources: list[dict] = []
    seen: set[str] = set()
    for li in cmpt.find_all("li", {"class": _LEGACY_SOURCE_LI_CLASS}):
        a = li.find("a", href=True)
        if a is None:
            continue
        href = str(a["href"])
        if not href or href == "#" or href in seen:
            continue
        seen.add(href)

        title = a.get("aria-label")
        if not title:
            title_div = li.find("div", {"class": "mNme1d"})
            title = title_div.get_text(" ", strip=True) if title_div else None
        publisher_div = li.find("div", {"class": "R8BTeb"})
        publisher = publisher_div.get_text(" ", strip=True) if publisher_div else ""
        snippet_span = li.find("span", {"class": "gxZfx"})
        snippet = snippet_span.get_text(" ", strip=True) if snippet_span else None

        sources.append(
            {
                "source_id": None,
                "url": href,
                "title": title or None,
                "snippet": snippet or None,
                "publisher": publisher,
                "favicon": None,
            }
        )
    return sources
