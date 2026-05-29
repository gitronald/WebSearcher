"""Parse the Knowledge Box component.

A wide-format panel surfaced on entity / topical queries. Sub_type covers a
large set of variants: featured results, featured snippet, unit converter,
sports, weather, finance, dictionary, translation, calculator, election
results, "things to know", and the generic panel layout.
"""

from selectolax.parser import Node

from .._slx import get_text, node_string, walk_descendants
from ..utils import slugify
from .general import parse_general_result


def parse_knowledge_panel(cmpt, sub_rank: int = 0) -> list:
    node: Node = cmpt.raw
    parsed: dict = {"type": "knowledge", "sub_rank": sub_rank}

    # Get embedded result if it exists. ``utils.get_text`` defaulted to
    # ``separator=" "`` -- preserve that explicitly so multi-fragment text is
    # space-joined (titles like "Donald Trump 45th and 47th U.S. President").
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
                urls.append(parse_alink(a))
        details["urls"] = urls

    h2 = node.css_first("h2")
    h2_text = get_text(h2) if h2 is not None else ""

    if (pxiwbd := node.css_first("div.pxiwBd")) is not None:
        parsed["sub_type"] = "featured_results"
        if not parsed["text"]:
            parsed["text"] = get_text(pxiwbd, " ", strip=True) or None
        primary = _first_external_link(pxiwbd)
        if primary:
            parsed["url"] = primary["url"]
    elif h2_text == "Featured snippet from the web" or node.css_first(
        "div.answered-question"
    ) is not None:
        parsed["sub_type"] = "featured_snippet"
        span = list(node.css("span"))
        details["text"] = _join_texts(span) if span else None

        # General component with no abstract
        g_div = node.css_first("div.g")
        if g_div is not None:
            parsed_general = parse_general_result(g_div)
            parsed_general = {
                k: v for k, v in parsed_general.items() if k in {"title", "url", "cite"}
            }
            parsed.update(parsed_general)

    elif h2_text == "Unit Converter":
        parsed["sub_type"] = "unit_converter"
        span = list(node.css("span"))
        details["text"] = _join_texts(span) if span else None

    elif h2_text == "Sports Results":
        parsed["sub_type"] = "sports"
        div = node.css_first("div.SwsxUd")
        # Original used bs4 ``.text`` (sep=""); preserve that (snapshots concat).
        details["text"] = get_text(div) if div is not None else None

    elif h2_text == "Weather Result":
        parsed["sub_type"] = "weather"

    elif h2_text == "Finance Results" or node.css_first(
        'div[id="knowledge-finance-wholepage__entity-summary"]'
    ) is not None:
        parsed["sub_type"] = "finance"

    elif node.css_first('div[data-attrid="DictionaryHeader"]') is not None or (
        (button := node.css_first('div[role="button"]')) is not None
        and (get_text(button) or "") == "Dictionary"
    ):
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
                    details["text"] = (
                        _join_texts(span).split("Translate")[0] if span else None
                    )

    elif h2_text in ("Translation Result", "Resultado de traducción"):
        parsed["sub_type"] = "translate"
        span = list(node.css("span"))
        details["text"] = _join_texts(span).split("Community Verified")[0] if span else None

    elif h2_text == "Calculator Result":
        parsed["sub_type"] = "calculator"

    elif details["heading"] == "2020 US election results":
        parsed["sub_type"] = "election"
        span = list(node.css("span"))
        details["text"] = _join_texts(span) if span else None

    elif (heading_span := node.css_first('span[role="heading"].IFnjPb')) is not None:
        if (get_text(heading_span) or "").strip() in (
            "Things to know",
            "Cosas que debes saber",
        ):
            parsed["sub_type"] = "things_to_know"
            details["heading"] = (get_text(heading_span) or "").strip()

    elif node.css_first("div.JNkvid") is not None and (
        section_heading := node.css_first('[role="heading"][aria-level="2"]')
    ) is not None:
        heading_text = get_text(section_heading, " ", strip=True) or ""
        # slugify first (whitespace-robust), then map the literal `&` token.
        parsed["sub_type"] = slugify(heading_text.lower(), sep="-").replace("-&-", "-and-")
        parsed["title"] = heading_text
        # Drop Google KG-navigation /search? links -- they're internal entity redirects.
        details["urls"] = [
            u for u in details.get("urls", []) if not u["url"].startswith("/search?")
        ]
        items = [
            get_text(h, " ", strip=True) or ""
            for h in node.css('[role="heading"][aria-level="3"]')
        ]
        if items:
            details["items"] = items

    else:
        parsed["sub_type"] = "panel"
        # bs4 ``find_all(["span","div","a"], string=True)`` matches tags whose
        # ``.string`` (single text-node child) is truthy. Walk descendants in
        # document order (not ``node.traverse`` -- that leaks beyond the subtree;
        # not ``node.css("span, div, a")`` -- comma selectors return tag-grouped,
        # not document-order). Check the single-string-child predicate in Python.
        div = [
            n
            for n in walk_descendants(node, include_text=False)
            if n.tag in ("span", "div", "a") and node_string(n) is not None
        ]
        details["text"] = _join_texts(div) if div else None

        text_divs = list(node.css("div.sinMW"))
        text_list = [t for t in (get_text(d, strip=True) for d in text_divs) if t]
        parsed["text"] = "<|>".join(text_list) if text_list else None
        # bs4 ``{"class": ["ZbhV9d", "HdbW6"]}`` = OR -> CSS comma selector.
        parsed["title"] = get_text(node.css_first("div.ZbhV9d, div.HdbW6"), " ", strip=True)

    img_div = node.css_first("div.img-brk")
    if img_div is not None:
        a = img_div.css_first("a")
        details["img_url"] = a.attributes.get("href") if a is not None else None
    else:
        details["img_url"] = None
    details["type"] = "panel"
    parsed["details"] = details

    return [parsed]


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


def parse_alink(a: Node) -> dict:
    return {"url": a.attributes["href"], "text": get_text(a, "|") or ""}
