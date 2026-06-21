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

import contextvars

from selectolax.lexbor import LexborNode as Node

from ..._slx import class_tokens, get_text
from ._ai_overview_payloads import extract_payloads

# Set by ``parse_serp`` so ``_root_html`` skips a full-document serialization
# per AI overview component. ``None`` outside that context (e.g. direct tests).
raw_serp_html: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "raw_serp_html", default=None
)


def parse_ai_overview(elem, sub_rank: int = 0) -> list[dict]:
    node: Node = elem
    parsed: dict = {
        "type": "ai_overview",
        "sub_rank": sub_rank,
        "title": None,
        "url": None,
        "cite": None,
    }

    content = node.css_first("div.mZJni")
    if content is not None:
        # Payload extraction serializes the whole document; only the current
        # DOM ships these JSON citation payloads, so skip it for legacy SERPs.
        payloads = extract_payloads(_root_html(node))
        type_a_by_src_id = _index_type_a_by_src_id(payloads)
        lede, lede_citations, sections = _extract_body(content, payloads)
        sources = _extract_sources(node, type_a_by_src_id)
    else:
        # Legacy SGE (2024) markup: the current-DOM body container is absent.
        lede, lede_citations, sections = _extract_body_legacy(node)
        sources = _extract_sources_legacy(node)

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
    if parsed["text"] is None and parsed["details"] is None and _is_unavailable(node):
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


def _is_unavailable(node: Node) -> bool:
    text = get_text(node, " ", strip=True) or ""
    return any(marker in text for marker in _UNAVAILABLE_MARKERS)


def _root_html(node: Node) -> str:
    """Document HTML for payload extraction.

    The ``lDPB.push`` fallback payload form lives in script tags outside the
    AI overview component, so we need the full document. ``parse_serp`` publishes
    the raw markup via a ``ContextVar`` (``raw_serp_html``); we fall back to
    serializing the document root when called outside that context (e.g.
    direct tests of the parser).
    """
    cached = raw_serp_html.get()
    if cached is not None:
        return cached
    cur = node
    while cur.parent is not None:
        cur = cur.parent
    return cur.html or ""


def _extract_body(content: Node, payloads: dict[str, dict]) -> tuple[str, list[dict], list[dict]]:
    """Walk the content area and split into lede + lede citations + sections."""
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
        for button in elem.css("button.rBl3me"):
            button.decompose()

        if _is_section_heading(elem):
            current = {
                "heading": get_text(elem, " ", strip=True) or "",
                "text": None,
                "hyperlinks": [],
                "citations": [],
            }
            sections.append(current)
            if button_citations:
                current["citations"].extend(button_citations)
            continue

        text = get_text(elem, " ", strip=True) or ""
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


def _collect_body_elements(content: Node) -> list[Node]:
    """Collect paragraph/heading/list elements from the body in document order."""
    self_id = content.mem_id
    paragraphs = [n for n in content.css(f"div.{_BODY_PARA_CLASS}") if n.mem_id != self_id]
    headings = [n for n in content.css(f"div.{_BODY_HEADING_CLASS}") if n.mem_id != self_id]
    lists: list[Node] = []
    for cls in _LIST_CLASSES:
        for elem in content.css(f"ul.{cls}, ol.{cls}"):
            if elem.mem_id != self_id:
                lists.append(elem)

    elements = paragraphs + headings + lists
    # Deduplicate (Y3BBE divs can nest inside one another in some layouts)
    # and drop elements whose ancestor is already in the set.
    elements = _drop_nested_descendants(elements)
    return sorted(elements, key=_doc_position)


def _drop_nested_descendants(elements: list[Node]) -> list[Node]:
    elem_ids = {e.mem_id for e in elements}
    kept = []
    for e in elements:
        parent = e.parent
        skip = False
        while parent is not None:
            if parent.mem_id in elem_ids:
                skip = True
                break
            parent = parent.parent
        if not skip:
            kept.append(e)
    return kept


def _doc_position(elem: Node) -> tuple:
    """Crude document position via ancestor chain indices."""
    path = []
    node: Node | None = elem
    while node is not None and node.parent is not None:
        siblings = list(node.parent.iter(include_text=False))
        node_id = node.mem_id
        idx = next((i for i, s in enumerate(siblings) if s.mem_id == node_id), 0)
        path.append(idx)
        node = node.parent
    return tuple(reversed(path))


def _is_section_heading(elem: Node) -> bool:
    if elem.tag != "div":
        return False
    cls = class_tokens(elem)
    if _BODY_HEADING_CLASS in cls:
        return True
    return elem.attributes.get("role") == "heading" and elem.attributes.get("aria-level") == "3"


def _collect_inline_links(elem: Node) -> list[dict]:
    """Collect anchors from inline body content (skips sources tray and #)."""
    links = []
    seen: set[str] = set()
    for a in elem.css("a[href]"):
        href = str(a.attributes["href"])
        if href == "#" or href.startswith("/search?"):
            continue
        if _find_parent_tag_class(a, "ul", "bTFeG") is not None:
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append({"url": href, "text": get_text(a, " ", strip=True) or ""})
    return links


def _find_parent_tag_class(node: Node, tag: str, cls: str) -> Node | None:
    """bs4 ``find_parent(tag, {"class": cls})``: walk ancestors only (never self),
    match on tag + class-token membership."""
    p = node.parent
    while p is not None:
        if p.tag == tag and cls in class_tokens(p):
            return p
        p = p.parent
    return None


def _extract_button_citations(elem: Node, payloads: dict[str, dict]) -> list[dict]:
    """Build citation dicts for ``button.rBl3me`` widgets within ``elem``."""
    citations: list[dict] = []
    for button in elem.css("button.rBl3me"):
        uuid_raw = button.attributes.get("data-icl-uuid")
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


def _button_publisher(button: Node) -> str | None:
    """Pull the publisher label from ``span.iFMVXd`` inside a ``rBl3me`` button."""
    span = button.css_first("span.iFMVXd")
    if span is None:
        return None
    text = get_text(span, " ", strip=True)
    return text or None


def _button_additional_count(button: Node) -> int:
    span = button.css_first("span.IjM6od")
    if span is None:
        return 0
    text = (get_text(span, " ", strip=True) or "").lstrip("+").strip()
    try:
        return int(text)
    except ValueError:
        return 0


def _index_type_a_by_src_id(payloads: dict[str, dict]) -> dict[str, dict]:
    """Flatten all Type-A payloads into a ``data-src-id -> entry`` map."""
    out: dict[str, dict] = {}
    for bucket in payloads.values():
        for entry in bucket.get("type_a", []):
            src_id = entry.get("source_id")
            if not src_id or src_id in out:
                continue
            out[src_id] = entry
    return out


def _extract_sources(node: Node, type_a_by_src_id: dict[str, dict]) -> list[dict]:
    """Build the sources list in tray (rank) order."""
    sources_ul = node.css_first("ul.bTFeG")
    if sources_ul is None:
        return []
    sources = []
    seen_src_ids: set[str] = set()
    for li in sources_ul.css("li.CyMdWb"):
        src_id_node = li.css_first("[data-src-id]")
        src_id_raw = src_id_node.attributes.get("data-src-id") if src_id_node is not None else None
        src_id = str(src_id_raw) if src_id_raw else None
        a = li.css_first("a[href]")
        href = str(a.attributes["href"]) if a is not None else None
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


def _tray_publisher(li: Node) -> str | None:
    span = li.css_first("span.Z1JFYc")
    if span is None:
        return None
    text = get_text(span, " ", strip=True)
    return text or None


# --- Legacy SGE (2024) markup ---------------------------------------------

_LEGACY_PARA_CLASS = "rPeykc"
_LEGACY_SOURCE_LI_CLASS = "LLtSOc"
_SOURCES_UL_CLASS = "zVKf0d"


def _extract_body_legacy(content: Node) -> tuple[str, list[dict], list[dict]]:
    """Walk the 2024 SGE body into lede + sections (no payload citations)."""
    self_id = content.mem_id
    paragraphs = [n for n in content.css(f"div.{_LEGACY_PARA_CLASS}") if n.mem_id != self_id]
    lists = [
        lst
        for lst in content.css("ul, ol")
        if lst.mem_id != self_id
        and _SOURCES_UL_CLASS not in class_tokens(lst)
        and _find_parent_tag_class(lst, "li", _LEGACY_SOURCE_LI_CLASS) is None
    ]
    elements = _drop_nested_descendants(paragraphs + lists)
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

        text = get_text(elem, " ", strip=True) or ""
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


def _legacy_section_heading(elem: Node) -> str | None:
    """Return the section-heading text if ``elem`` wraps a SGE section heading."""
    heading = elem.css_first('[role="heading"]')
    if heading is None:
        return None
    if "Fzsovc" in class_tokens(heading):
        return None
    text = get_text(heading, " ", strip=True)
    return text or None


def _extract_sources_legacy(node: Node) -> list[dict]:
    """Build the sources list from the legacy ``li.LLtSOc`` tray cards."""
    sources: list[dict] = []
    seen: set[str] = set()
    for li in node.css(f"li.{_LEGACY_SOURCE_LI_CLASS}"):
        a = li.css_first("a[href]")
        if a is None:
            continue
        href = str(a.attributes["href"])
        if not href or href == "#" or href in seen:
            continue
        seen.add(href)

        title = a.attributes.get("aria-label")
        if not title:
            title_div = li.css_first("div.mNme1d")
            title = get_text(title_div, " ", strip=True) if title_div is not None else None
        publisher_div = li.css_first("div.R8BTeb")
        publisher = get_text(publisher_div, " ", strip=True) if publisher_div is not None else ""
        snippet_span = li.css_first("span.gxZfx")
        snippet = get_text(snippet_span, " ", strip=True) if snippet_span is not None else None

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
