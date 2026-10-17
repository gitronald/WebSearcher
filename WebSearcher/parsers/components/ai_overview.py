"""Parse the AI Overview component.

Google's AI Overview is a synthesized answer panel that appears at or near the
top of a SERP. It comes in three states:

- ``flat`` — a single answer block (intro paragraph + optional bullet list)
- ``sectioned`` — an intro lede followed by N section subheadings (each with its
  own bullet list and optional inline links)
- ``unavailable`` — the component was detected but Google declined to synthesize
  an overview ("An AI Overview is not available for this search"). No body or
  sources; recorded explicitly so a decline is distinguishable from a parser
  miss (which stays ``flat`` with empty output).

The flat and sectioned layouts share a "Sources" tray at the bottom that lists the publishers the
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

The role-heading layout (2026-10) keeps ``div.mZJni`` but renames the markup
inside it, so it runs through the current-DOM path with an extra class per
role (see the ``_BODY_*``/``_CITATION_*`` constants). Its sources are
``div[data-src-id]`` cards with no ``ul.bTFeG`` tray, and its payloads carry
``/goto?url=`` redirects in place of full URLs; ``_index_full_url_by_goto``
recovers the full URL where a payload header names it.
"""

from __future__ import annotations

import contextvars
from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import class_tokens, get_text
from ._ai_overview_payloads import extract_payloads

# Set by ``parse_serp`` so ``_root_html`` skips a full-document serialization
# per AI overview component. ``None`` outside that context (e.g. direct tests).
raw_serp_html: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "raw_serp_html", default=None
)


def parse_ai_overview(elem: Node, sub_rank: int = 0) -> list[dict[str, Any]]:
    node: Node = elem
    parsed: dict[str, Any] = {
        "type": "ai_overview",
        "sub_rank": sub_rank,
        "title": None,
        "url": None,
        "cite": None,
    }

    content = node.css_first("div.mZJni")
    if content is not None:
        overview = extract_overview(content, node)
    else:
        # Legacy SGE (2024) markup: the current-DOM body container is absent.
        lede, lede_citations, sections = _extract_body_legacy(node)
        overview = _overview_fields(
            lede, sections, lede_citations, _extract_sources_legacy(node), None
        )

    parsed["text"] = overview.pop("text")
    parsed["sub_type"] = "sectioned" if "sections" in overview else "flat"
    parsed["details"] = {"type": "ai_overview", **overview} if overview else None

    # Distinguish a genuine "Google declined to generate" panel from a parser
    # miss: both otherwise yield empty output. The decline message is shipped
    # (hidden) on every AI-overview page, so it is only meaningful when no
    # content was extracted.
    if parsed["text"] is None and parsed["details"] is None and _is_unavailable(node):
        parsed["sub_type"] = "unavailable"

    return [parsed]


def extract_overview(content: Node, scope: Node) -> dict[str, Any]:
    """Parse a current-DOM overview body (``div.mZJni``).

    Returns the lede as ``text`` plus whichever of ``sections``, ``citations``,
    ``sources``, and ``follow_up`` are present. ``scope`` bounds the source
    cards: the whole component for the main overview, the question for an
    answer embedded in people-also-ask. Citation widgets are decomposed from
    ``content`` as the body is read.
    """
    # Payload extraction serializes the whole document; only the current DOM
    # ships these JSON citation payloads, so legacy SERPs never reach it.
    payloads = extract_payloads(_root_html(content))
    type_a_by_src_id = _index_type_a_by_src_id(payloads)
    full_url_by_goto = _index_full_url_by_goto(payloads)
    lede, lede_citations, sections = _extract_body(content, payloads, full_url_by_goto)
    sources = _extract_sources(scope, type_a_by_src_id, full_url_by_goto)
    return _overview_fields(lede, sections, lede_citations, sources, _extract_follow_up(content))


def _overview_fields(
    lede: str,
    sections: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    follow_up: str | None,
) -> dict[str, Any]:
    """``text`` plus the non-empty detail fields, in output order."""
    fields: dict[str, Any] = {"text": lede or None}
    for key, value in (
        ("sections", sections),
        ("citations", citations),
        ("sources", sources),
        ("follow_up", follow_up),
    ):
        if value:
            fields[key] = value
    return fields


# Body markup per layout: ``Y3BBE``/``otQkpb``/``KsbFXc``/``IaGLZe`` in the
# Fzsovc layout; ``n6owBd`` paragraphs, ``div[role=heading][aria-level=3]``
# headings, and ``XSq4R``/``T9WCjf`` lists in the role-heading layout (2026-10).
_BODY_PARA_CLASSES = ("Y3BBE", "n6owBd")
_BODY_HEADING_CLASS = "otQkpb"
_BODY_HEADING_CSS = f'div.{_BODY_HEADING_CLASS}, div[role="heading"][aria-level="3"]'
_LIST_CLASSES = ("KsbFXc", "IaGLZe", "XSq4R", "T9WCjf")

# The role-heading layout closes with a follow-up prompt ("Would you like to
# know ...") in this wrapper. It invites a next query rather than answering
# this one, so it is kept out of the body text and reported as
# ``details["follow_up"]``.
_FOLLOW_UP_CLASS = "AHmQrc"

# Citation widgets: ``button.rBl3me`` (publisher ``span.iFMVXd``, count
# ``span.IjM6od``) in the Fzsovc layout; ``button.vDOt8c`` (publisher
# ``span.QNca8b``, count ``span.OkUHJe``) in the role-heading layout, wrapped
# in ``span.NMq1me`` with a hidden ``a.PMDqCb`` to the lead source.
_CITATION_BUTTON_CSS = "button.rBl3me, button.vDOt8c"
_CITATION_PUBLISHER_CSS = "span.iFMVXd, span.QNca8b"
_CITATION_COUNT_CSS = "span.IjM6od, span.OkUHJe"
_CITATION_STRIP_CSS = "button.rBl3me, span.NMq1me"

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


def _extract_follow_up(content: Node) -> str | None:
    """Text of the closing follow-up prompt, or None when there is none."""
    wrapper = content.css_first(f"div.{_FOLLOW_UP_CLASS}")
    if wrapper is None:
        return None
    return get_text(wrapper, " ", strip=True) or None


def _extract_body(
    content: Node, payloads: dict[str, dict[str, Any]], full_url_by_goto: dict[str, str]
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Walk the content area and split into lede + lede citations + sections."""
    elements = _collect_body_elements(content)
    if not elements:
        return "", [], []

    lede_parts: list[str] = []
    lede_citations: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for elem in elements:
        button_citations = _extract_button_citations(elem, payloads)
        # Strip citation widgets before text extraction so the "Publisher +N"
        # label does not leak into the section text, nor their hidden source
        # anchors into the inline links.
        for widget in elem.css(_CITATION_STRIP_CSS):
            widget.decompose()

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
        hyperlinks = _collect_inline_links(elem, full_url_by_goto)

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
    paragraphs: list[Node] = []
    for cls in _BODY_PARA_CLASSES:
        paragraphs.extend(n for n in content.css(f"div.{cls}") if n.mem_id != self_id)
    headings = [n for n in content.css(_BODY_HEADING_CSS) if n.mem_id != self_id]
    lists: list[Node] = []
    for cls in _LIST_CLASSES:
        for elem in content.css(f"ul.{cls}, ol.{cls}"):
            if elem.mem_id != self_id:
                lists.append(elem)

    # Keyed by mem_id: a comma-union selector yields an element once per
    # selector it matches (``otQkpb`` headings also carry the role attributes).
    elements = list({e.mem_id: e for e in paragraphs + headings + lists}.values())
    # Drop elements whose ancestor is already in the set (Y3BBE divs can nest
    # inside one another in some layouts).
    elements = _drop_nested_descendants(elements)
    elements = [e for e in elements if _find_parent_tag_class(e, "div", _FOLLOW_UP_CLASS) is None]
    return sorted(elements, key=_doc_position)


def _drop_nested_descendants(elements: list[Node]) -> list[Node]:
    elem_ids = {e.mem_id for e in elements}
    kept: list[Node] = []
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


def _doc_position(elem: Node) -> tuple[int, ...]:
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


def _collect_inline_links(
    elem: Node, full_url_by_goto: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Collect anchors from inline body content (skips sources tray and #).

    ``/goto?url=`` redirects (role-heading layout) are swapped for the full
    URL when the citation payloads resolve them.
    """
    full_urls = full_url_by_goto or {}
    links = []
    seen: set[str] = set()
    for a in elem.css("a[href]"):
        href = str(a.attributes["href"])
        if href == "#" or href.startswith("/search?"):
            continue
        if _find_parent_tag_class(a, "ul", "bTFeG") is not None:
            continue
        url = full_urls.get(href, href)
        if url in seen:
            continue
        seen.add(url)
        links.append({"url": url, "text": get_text(a, " ", strip=True) or ""})
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


def _extract_button_citations(
    elem: Node, payloads: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Build citation dicts for the citation buttons within ``elem``."""
    citations: list[dict[str, Any]] = []
    for button in elem.css(_CITATION_BUTTON_CSS):
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
    """Pull the publisher label from inside a citation button."""
    span = button.css_first(_CITATION_PUBLISHER_CSS)
    if span is None:
        return None
    text = get_text(span, " ", strip=True)
    return text or None


def _button_additional_count(button: Node) -> int:
    span = button.css_first(_CITATION_COUNT_CSS)
    if span is None:
        return 0
    text = (get_text(span, " ", strip=True) or "").lstrip("+").strip()
    try:
        return int(text)
    except ValueError:
        return 0


def _index_type_a_by_src_id(payloads: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Flatten all Type-A payloads into a ``data-src-id -> entry`` map."""
    out: dict[str, dict[str, Any]] = {}
    for bucket in payloads.values():
        for entry in bucket.get("type_a", []):
            src_id = entry.get("source_id")
            if not src_id or src_id in out:
                continue
            out[src_id] = entry
    return out


def _index_full_url_by_goto(payloads: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Map ``/goto?url=`` redirects to full URLs (role-heading layout).

    That layout's Type-A entries carry a redirect where the full URL used to
    be. A header names the full URL of its button's lead source only: the
    bucket's first Type-A entry, when that entry agrees with the header on
    publisher and domain. A lead source whose entry sits in another button's
    bucket is matched across buckets when exactly one redirect fits. Anything
    else stays a redirect (about half the sources in the 2026-10 captures).
    """
    redirects = {
        entry["url"]: entry
        for bucket in payloads.values()
        for entry in bucket.get("type_a", [])
        if (entry.get("url") or "").startswith("/goto?")
    }
    out: dict[str, str] = {}
    unmatched: list[dict[str, Any]] = []
    for bucket in payloads.values():
        header = bucket.get("header") or {}
        if not header.get("url"):
            continue
        type_a = bucket.get("type_a", [])
        lead = type_a[0] if type_a else None
        if lead is not None and lead.get("url") in redirects and _names_source(header, lead):
            out[lead["url"]] = header["url"]
        else:
            unmatched.append(header)
    for header in unmatched:
        fits = [url for url, entry in redirects.items() if _names_source(header, entry)]
        if len(fits) == 1:
            out.setdefault(fits[0], header["url"])
    return out


def _names_source(header: dict[str, Any], entry: dict[str, Any]) -> bool:
    """Whether a header's full URL can belong to a Type-A entry."""
    domain = entry.get("domain")
    return (
        entry.get("publisher") == header.get("publisher")
        and bool(domain)
        and header["url"].startswith(domain)
    )


def _extract_sources(
    node: Node,
    type_a_by_src_id: dict[str, dict[str, Any]],
    full_url_by_goto: dict[str, str],
) -> list[dict[str, Any]]:
    """Build the sources list in tray (rank) order."""
    sources_ul = node.css_first("ul.bTFeG")
    if sources_ul is not None:
        cards = sources_ul.css("li.CyMdWb")
    else:
        # Role-heading layout: each source card is a ``div[data-src-id]``, in a
        # list below the body (``cRH23c``) or a panel inside it (``fSJHKf``).
        cards = node.css("div[data-src-id]")
    sources = []
    seen_src_ids: set[str] = set()
    for card in cards:
        src_id_node = card if "data-src-id" in card.attributes else card.css_first("[data-src-id]")
        src_id_raw = src_id_node.attributes.get("data-src-id") if src_id_node is not None else None
        src_id = str(src_id_raw) if src_id_raw else None
        a = card.css_first("a[href]")
        href = str(a.attributes["href"]) if a is not None else None
        if not href or href == "#":
            continue
        if src_id and src_id in seen_src_ids:
            continue
        if src_id:
            seen_src_ids.add(src_id)

        payload: dict[str, Any] = type_a_by_src_id.get(src_id, {}) if src_id else {}
        publisher = payload.get("publisher") or _tray_publisher(card) or ""
        url = payload.get("url") or href
        sources.append(
            {
                "source_id": src_id,
                "url": full_url_by_goto.get(url, url),
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


def _extract_body_legacy(content: Node) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
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
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

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


def _extract_sources_legacy(node: Node) -> list[dict[str, Any]]:
    """Build the sources list from the legacy ``li.LLtSOc`` tray cards."""
    sources: list[dict[str, Any]] = []
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
