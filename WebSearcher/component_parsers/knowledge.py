"""Parse the Knowledge Box component.

A wide-format panel surfaced on entity / topical queries. Sub_type covers a
large set of variants: featured results, featured snippet, unit converter,
sports, weather, finance, dictionary, translation, calculator, election
results, "things to know", and the generic panel layout.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text, node_string, walk_descendants
from ..utils import slugify
from ._common import parse_alink
from .general import parse_general_result


def parse_knowledge_panel(elem, sub_rank: int = 0) -> list:
    node: Node = elem

    # kp-wholepage VisualDigest band: a digest of entity facts + a featured web
    # result + a social post + an image collage. It carries multiple linked
    # sub-results, so it parses to multiple rows -- handle it before the
    # single-row handler chain below.
    if node.css_first('[data-attrid^="VisualDigest"]') is not None:
        return _parse_visual_digest(node)

    # kp-wholepage music-artist section tabs (songs / albums / events): a heading
    # plus a role="list" of items that the generic panel parse collapses to an
    # empty shell. Emit one row per item instead.
    section_rows = _parse_music_section(node)
    if section_rows is not None:
        return section_rows

    parsed: dict = {"type": "knowledge", "sub_rank": sub_rank}

    # Embedded result: space-join multi-fragment text so titles like
    # "Donald Trump 45th and 47th U.S. President" stay readable.
    result = node.css_first("div.rc")
    if result is not None:
        h3 = result.css_first("h3")
        a = result.css_first("a")
        cite_el = result.css_first("cite")
        parsed["title"] = get_text(h3, " ", strip=True) if h3 is not None else None
        parsed["url"] = a.attributes.get("href") if a is not None else None
        parsed["cite"] = get_text(cite_el, " ", strip=True) if cite_el is not None else None

    parsed["text"] = get_text(
        node.css_first('div[role="heading"][aria-level="3"]'), " ", strip=True
    )

    details: dict = {}

    heading = node.css_first('div[role="heading"]')
    details["heading"] = get_text(heading, " ", strip=True) if heading is not None else None

    alinks = list(node.css("a"))
    if alinks:
        urls = []
        seen_urls: set[str] = set()
        for a in alinks:
            href = a.attributes.get("href")
            if href is not None and href != "#" and href not in seen_urls:
                seen_urls.add(href)
                urls.append(parse_alink(a, "|"))
        details["urls"] = urls

    h2 = node.css_first("h2")
    h2_text: str = get_text(h2) or ""

    # Ordered detect-and-handle dispatch (cf. ``classifiers/main.py``): the first
    # handler that recognizes the panel populates ``parsed``/``details`` and
    # returns ``True``, consuming the chain. ``_subtype_panel`` is the fallback
    # when no specific handler claims the panel.
    for handler in _SUBTYPE_HANDLERS:
        if handler(node, parsed, details, h2_text):
            break
    else:
        _subtype_panel(node, parsed, details, h2_text)

    img_div = node.css_first("div.img-brk")
    if img_div is not None:
        a = img_div.css_first("a")
        details["img_url"] = a.attributes.get("href") if a is not None else None
    else:
        details["img_url"] = None
    details["type"] = "panel"
    parsed["details"] = details

    return [parsed]


# --- sub_type handlers -----------------------------------------------------
#
# Each handler inspects ``node`` and, if it recognizes its sub_type, mutates
# ``parsed`` / ``details`` and returns ``True`` (consuming the dispatch chain).
# Returning ``True`` *without* setting ``sub_type`` is intentional for the
# "things to know" case: a matching heading-span container is claimed even when
# its text is not in the known set, so the panel fallback does not also run.


def _subtype_wholepage_header(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    """The kp-wholepage panel header: entity title, descriptor, and the tab nav
    strip (Overview / Songs / Albums / Events / ...).

    Scoped to the whole-page header by the ``kp-wholepage-osrp`` wrapper plus a
    ``subtitle`` fact, so regular knowledge panels (no wholepage wrapper) and the
    section tabs (no ``subtitle``) are left to their own handlers. Emits a clean
    title + descriptor instead of the tab-label mashup the generic fallback
    produced, with the tab labels in ``details``.
    """
    if node.css_first("div.kp-wholepage-osrp") is None:
        return False
    subtitle_el = node.css_first('[data-attrid="subtitle"]')
    if subtitle_el is None:
        return False

    parsed["sub_type"] = "panel"
    title_el = node.css_first('[data-attrid="title"]')
    parsed["title"] = get_text(title_el, " ", strip=True) if title_el is not None else None
    subtitle = get_text(subtitle_el, " ", strip=True) or None
    parsed["text"] = subtitle
    details["subtitle"] = subtitle

    # Tab labels live in the role="tab" strip (one node per tab, in document
    # order). A plain span scan would also pick up header chrome ("Send
    # feedback", "Claim this knowledge panel", "About this result"), so scope to
    # the tablist.
    tabs = [label for tab in node.css('[role="tab"]') if (label := get_text(tab, " ", strip=True))]
    if tabs:
        details["tabs"] = tabs
    return True


def _subtype_featured_results(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    pxiwbd = node.css_first("div.pxiwBd")
    if pxiwbd is None:
        return False
    parsed["sub_type"] = "featured_results"
    if not parsed["text"]:
        parsed["text"] = get_text(pxiwbd, " ", strip=True) or None
    primary = _first_external_link(pxiwbd)
    if primary:
        parsed["url"] = primary["url"]
    return True


def _subtype_featured_snippet(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    if not (
        h2_text == "Featured snippet from the web"
        or node.css_first("div.answered-question") is not None
    ):
        return False
    parsed["sub_type"] = "featured_snippet"
    span = list(node.css("span"))
    details["text"] = _join_texts(span) if span else None

    # General component with no abstract
    g_div = node.css_first("div.g")
    if g_div is not None:
        parsed_general = parse_general_result(g_div)
        parsed_general = {k: v for k, v in parsed_general.items() if k in {"title", "url", "cite"}}
        parsed.update(parsed_general)
    return True


def _subtype_unit_converter(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    if h2_text != "Unit Converter":
        return False
    parsed["sub_type"] = "unit_converter"
    span = list(node.css("span"))
    details["text"] = _join_texts(span) if span else None
    return True


def _subtype_sports(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    if h2_text != "Sports Results":
        return False
    parsed["sub_type"] = "sports"
    div = node.css_first("div.SwsxUd")
    # Original used bs4 ``.text`` (sep=""); preserve that (snapshots concat).
    details["text"] = get_text(div) if div is not None else None
    return True


def _subtype_weather(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    if h2_text != "Weather Result":
        return False
    parsed["sub_type"] = "weather"
    return True


def _subtype_finance(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    if not (
        h2_text == "Finance Results"
        or node.css_first('div[id="knowledge-finance-wholepage__entity-summary"]') is not None
    ):
        return False
    parsed["sub_type"] = "finance"
    return True


def _subtype_dictionary(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    is_dictionary = node.css_first('div[data-attrid="DictionaryHeader"]') is not None or (
        (button := node.css_first('div[role="button"]')) is not None
        and (get_text(button) or "") == "Dictionary"
    )
    if not is_dictionary:
        return False
    parsed["sub_type"] = "dictionary"
    # Modern dictionary panels expose structured data-attrid entries.
    entry = node.css_first('[data-attrid="EntryHeader"]')
    if entry is not None:
        # "cis·tern / ˈsistərn / Learn to pronounce" -> "cistern"
        word = (get_text(entry, " ", strip=True) or "").split("/")[0].replace("·", "").strip()
        parsed["title"] = word or None
    definitions = [
        text
        for d in node.css('[data-attrid="SenseDefinition"]')
        if (text := get_text(d, " ", strip=True))
    ]
    if definitions:
        parsed["text"] = " | ".join(definitions)
        details["text"] = parsed["text"]
    else:
        # Legacy layout fallback.
        vmod = node.css_first("div.vmod")
        if vmod is not None:
            details["text"] = (get_text(vmod, " ", strip=True) or "").split("Translate")[0]
        else:
            span_first = node.css_first('span[jsslot=""]')
            if span_first is not None:
                span = list(span_first.css("span"))
                details["text"] = _join_texts(span).split("Translate")[0] if span else None
    return True


def _subtype_translate(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    if h2_text not in ("Translation Result", "Resultado de traducción"):
        return False
    parsed["sub_type"] = "translate"
    span = list(node.css("span"))
    details["text"] = _join_texts(span).split("Community Verified")[0] if span else None
    return True


def _subtype_calculator(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    if h2_text != "Calculator Result":
        return False
    parsed["sub_type"] = "calculator"
    return True


def _subtype_election(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    if details["heading"] != "2020 US election results":
        return False
    parsed["sub_type"] = "election"
    span = list(node.css("span"))
    details["text"] = _join_texts(span) if span else None
    return True


def _subtype_things_to_know(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    heading_span = node.css_first('span[role="heading"].IFnjPb')
    if heading_span is None:
        return False
    # Claim the panel even if the heading text is not recognized (no sub_type).
    if (get_text(heading_span) or "").strip() in (
        "Things to know",
        "Cosas que debes saber",
    ):
        parsed["sub_type"] = "things_to_know"
        details["heading"] = (get_text(heading_span) or "").strip()
    return True


def _subtype_dynamic_section(node: Node, parsed: dict, details: dict, h2_text: str) -> bool:
    if node.css_first("div.JNkvid") is None:
        return False
    # A whole-page entity panel (kp-wholepage-osrp) is a generic "panel": an internal
    # subcard (e.g. a 'People also search for' carousel, or a feedback affordance whose
    # heading precedes it in document order) is a section of the panel, not the panel's
    # defining sub_type. Defer to the ``_subtype_panel`` fallback so the whole component
    # stays ``panel`` instead of inheriting a subcard/affordance heading.
    if node.css_first("div.kp-wholepage-osrp") is not None:
        return False
    section_heading = node.css_first('[role="heading"][aria-level="2"]')
    if section_heading is None:
        # JNkvid without a section heading falls through to the panel fallback.
        return False
    heading_text = get_text(section_heading, " ", strip=True) or ""
    # slugify first (whitespace-robust), then map the literal `&` token.
    parsed["sub_type"] = slugify(heading_text.lower(), sep="-").replace("-&-", "-and-")
    parsed["title"] = heading_text
    # Drop Google KG-navigation /search? links -- they're internal entity redirects.
    details["urls"] = [u for u in details.get("urls", []) if not u["url"].startswith("/search?")]
    items = [
        get_text(h, " ", strip=True) or "" for h in node.css('[role="heading"][aria-level="3"]')
    ]
    if items:
        details["items"] = items
    return True


def _subtype_panel(node: Node, parsed: dict, details: dict, h2_text: str) -> None:
    """Fallback handler: the generic panel layout (no specific sub_type matched)."""
    parsed["sub_type"] = "panel"
    # bs4 ``find_all(["span","div","a"], string=True)`` matches tags whose
    # ``.string`` (single text-node child) is truthy. Walk descendants in
    # document order (not ``node.traverse`` -- that leaks beyond the subtree;
    # not ``node.css("span, div, a")`` -- comma selectors return tag-grouped,
    # not document-order). Check the single-string-child predicate in Python.
    div = [
        n
        for n in walk_descendants(node)
        if n.tag in ("span", "div", "a") and node_string(n) is not None
    ]
    details["text"] = _join_texts(div) if div else None

    text_divs = list(node.css("div.sinMW"))
    text_list = [t for t in (get_text(d, strip=True) for d in text_divs) if t]
    parsed["text"] = "<|>".join(text_list) if text_list else None
    # bs4 ``{"class": ["ZbhV9d", "HdbW6"]}`` = OR -> CSS comma selector.
    parsed["title"] = get_text(node.css_first("div.ZbhV9d, div.HdbW6"), " ", strip=True)


# Evaluated in order; first to return ``True`` wins (cf. the original if/elif).
# ``_subtype_wholepage_header`` is last so the specialized handlers above still
# claim a wholepage panel that is really a dictionary / finance / etc.; it only
# catches the generic entity header before the ``_subtype_panel`` fallback.
_SUBTYPE_HANDLERS = (
    _subtype_featured_results,
    _subtype_featured_snippet,
    _subtype_unit_converter,
    _subtype_sports,
    _subtype_weather,
    _subtype_finance,
    _subtype_dictionary,
    _subtype_translate,
    _subtype_calculator,
    _subtype_election,
    _subtype_things_to_know,
    _subtype_dynamic_section,
    _subtype_wholepage_header,
)


# Known VisualDigest sub-result suffixes -> a stable ``kind``. Unknown suffixes
# fall back to a slug of the suffix so a new sub-result type is captured (with a
# best-effort kind) rather than silently dropped.
_VISUAL_DIGEST_KIND = {
    "FirstImageResult": "image",
    "ImageResult": "image",
    "WebResult": "web",
    "VideoResult": "video",
    "SocialMediaResult": "social",
}


def _visual_digest_kind(suffix: str) -> str:
    if suffix in _VISUAL_DIGEST_KIND:
        return _VISUAL_DIGEST_KIND[suffix]
    return (suffix[: -len("Result")] if suffix.endswith("Result") else suffix).lower()


def _parse_visual_digest(node: Node) -> list:
    """Parse a kp-wholepage VisualDigest band (the ``featured_results`` panel).

    The band is a ``div.pxiwBd`` container whose sub-results -- an image collage,
    a featured web result, a video, entity facts (Age, Genre, Artist, ...), and a
    social post -- are siblings, not nested under the web result. Each becomes its
    own ``sub_rank`` row of one ``featured_results`` component, in document order;
    a per-row ``details["kind"]`` records which sub-result it is. Any
    ``VisualDigest*`` sub-result is handled (kind derived from the attrid) so a
    new variant is captured rather than dropped. Image thumbnails are lazy-loaded
    1x1 gifs in the static HTML, so only the caption is recoverable.
    """
    results: list[dict] = []
    emitted: set[int] = set()
    for n in node.css("[data-attrid]"):
        attrid = n.attributes.get("data-attrid") or ""
        is_digest = attrid.startswith("VisualDigest")
        is_fact = attrid.startswith("lab/fact/")
        if not (is_digest or is_fact):
            continue

        # Skip nodes nested inside an already-emitted sub-result (the outermost
        # match per sub-result wins; guards against nested data-attrid markers).
        p, nested = n.parent, False
        while p is not None and p.mem_id != node.mem_id:
            if p.mem_id in emitted:
                nested = True
                break
            p = p.parent
        if nested:
            continue

        if is_fact:
            # Facts render as "Label|Value" (e.g. "Age|29 years", "Genre|Pop").
            parts = [p for p in (get_text(n, "|", strip=True) or "").split("|") if p]
            if len(parts) < 2:
                continue
            label, value = parts[0], parts[-1]
            url, text = None, f"{label}: {value}"
            details = {"kind": "fact", "label": label, "value": value}
        else:
            kind = _visual_digest_kind(attrid[len("VisualDigest") :])
            text = get_text(n, " ", strip=True) or None
            if kind == "image":
                url = None
                if not text:  # empty image-result placeholder
                    continue
            else:
                a = n.css_first("a[href]")
                url = a.attributes.get("href") if a is not None else None
                if url is None and not text:
                    continue
            details = {"kind": kind}

        emitted.add(n.mem_id)
        results.append(
            {
                "type": "knowledge",
                "sub_type": "featured_results",
                "sub_rank": len(results),
                "url": url,
                "text": text,
                "details": details,
            }
        )
    return results


# --- kp-wholepage music-artist sections (songs / albums / events) -----------
#
# Each is a knowledge component holding a ``[data-attrid="kc:/music/artist:<key>"]``
# block with a ``role="list"`` of ``role="listitem"`` items. The section key maps
# to a sub_type; a per-section item parser pulls the item's fields. Sections
# without a registered item parser fall through to the generic handler chain.

_MUSIC_SECTION_SUBTYPE = {
    "songs": "songs",
    "albums": "albums",
    "upcoming events": "events",
}


def _list_strings(node: Node, tag: str) -> list[str]:
    """Stripped single-string text of ``tag`` descendants, dropping separators."""
    out = []
    for el in node.css(tag):
        s = node_string(el)
        if s and (s := s.strip()) and s != "·":  # middot separator
            out.append(s)
    return out


def _parse_song_item(li: Node) -> dict:
    """A song listitem -> ``{title, album?, year?}``.

    The year is a trailing standalone 4-digit span; the album is the remaining
    span (some songs carry only one or the other).
    """
    titles = _list_strings(li, "div")
    spans = _list_strings(li, "span")
    year = spans.pop() if spans and spans[-1].isdigit() and len(spans[-1]) == 4 else None
    album = spans[0] if spans else None
    item = {"title": titles[0] if titles else None}
    if album:
        item["album"] = album
    if year:
        item["year"] = year
    return item


def _parse_event_item(li: Node) -> dict:
    """An upcoming-event listitem -> ``{date, time, location, venue}``.

    The four fields render as single-string divs in that fixed order (some
    events omit a trailing field).
    """
    fields = _list_strings(li, "div")
    keys = ("date", "time", "location", "venue")
    return {k: v for k, v in zip(keys, fields)}


def _parse_album_item(li: Node) -> dict:
    """An album listitem -> ``{title, year}``.

    Visually an image grid, but the cover thumbnails are lazy-loaded 1x1 gifs in
    the static HTML (no usable src), so only title + year are recoverable. The
    year renders twice (visible + duplicate); take the first 4-digit token.
    """
    divs = _list_strings(li, "div")
    item = {"title": divs[0] if divs else None}
    year = next((d for d in divs[1:] if d.isdigit() and len(d) == 4), None)
    if year:
        item["year"] = year
    return item


_MUSIC_ITEM_PARSERS = {
    "songs": _parse_song_item,
    "events": _parse_event_item,
    "albums": _parse_album_item,
}


def _parse_music_section(node: Node) -> list | None:
    """Parse a kp-wholepage music-artist section into a single component row.

    The section is kept as one ``knowledge`` row carrying the section label as
    ``title``, with the per-item dicts stashed in ``details`` as
    ``{"type": <sub_type>, "items": [...]}``. Returns ``None`` (so the caller
    falls through to the generic handlers) when the component is not a recognized
    music section or the section has no registered item parser yet.
    """
    block = node.css_first('[data-attrid^="kc:/music/artist:"]')
    if block is None:
        return None
    key = (block.attributes.get("data-attrid") or "").split(":")[-1]
    sub_type = _MUSIC_SECTION_SUBTYPE.get(key)
    item_fn = _MUSIC_ITEM_PARSERS.get(sub_type) if sub_type else None
    if item_fn is None:
        return None

    items = block.css('[role="listitem"]')
    if not items:
        return None

    heading = node.css_first('[role="heading"]')
    parsed_items = [item_fn(li) for li in items]
    return [
        {
            "type": "knowledge",
            "sub_type": sub_type,
            "sub_rank": 0,
            "title": get_text(heading, " ", strip=True) if heading is not None else None,
            "text": None,
            "details": {"type": sub_type, "items": parsed_items},
        }
    ]


def _join_texts(div: list[Node]) -> str:
    return "|".join(get_text(d, separator=" ") or "" for d in div if (get_text(d) or ""))


def _first_external_link(node: Node) -> dict | None:
    """Return the first absolute (external) anchor (url + text) within ``node``.

    Skips root-relative Google links (``/search?``, ``/intl/...`` disclaimers,
    etc.) — only ``http(s)://`` targets count.
    """
    for a in node.css("a[href]"):
        href = str(a.attributes["href"])
        if not href.startswith(("http://", "https://")):
            continue
        return {"url": href, "text": get_text(a, " ", strip=True) or ""}
    return None
