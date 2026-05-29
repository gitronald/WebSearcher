"""Parse the Knowledge Box component.

A wide-format panel surfaced on entity / topical queries. Sub_type covers a
large set of variants: featured results, featured snippet, unit converter,
sports, weather, finance, dictionary, translation, calculator, election
results, "things to know", and the generic panel layout.
"""

from selectolax.parser import Node

from ..utils import get_link, get_text, slugify
from .general import parse_general_result


def parse_knowledge_panel(cmpt: Node, sub_rank: int = 0) -> list:
    parsed: dict = {"type": "knowledge", "sub_rank": sub_rank}

    # Get embedded result if it exists
    result = cmpt.find("div", {"class": "rc"})
    if result:
        parsed["title"] = get_text(result, "h3", strip=True)
        parsed["url"] = get_link(result)
        parsed["cite"] = get_text(result, "cite", strip=True)

    parsed["text"] = get_text(cmpt, "div", {"role": "heading", "aria-level": "3"}, strip=True)

    details: dict = {}

    heading = cmpt.find("div", {"role": "heading"})
    details["heading"] = heading.get_text(" ", strip=True) if heading else None

    alinks = cmpt.find_all("a")
    if alinks:
        urls = []
        seen_urls = set()
        for a in alinks:
            if "href" in a.attrs and a["href"] != "#":
                if a["href"] not in seen_urls:
                    seen_urls.add(a["href"])
                    urls.append(parse_alink(a))
        details["urls"] = urls

    h2 = cmpt.find("h2")
    h2_text = h2.text if h2 else ""

    if (pxiwbd := cmpt.find("div", {"class": "pxiwBd"})) is not None:
        parsed["sub_type"] = "featured_results"
        # Heterogeneous panel (video carousel, lyrics, featured snippet); the
        # primary link's text bundles title + description, so we recover text +
        # url only and leave the unreliable title unset. Prefer the heading text
        # already captured above (a finance/ticker pxiwBd is digit noise).
        if not parsed["text"]:
            parsed["text"] = pxiwbd.get_text(" ", strip=True) or None
        primary = _first_external_link(pxiwbd)
        if primary:
            parsed["url"] = primary["url"]
    elif h2_text == "Featured snippet from the web" or cmpt.find(
        "div", {"class": "answered-question"}
    ):
        parsed["sub_type"] = "featured_snippet"
        span = cmpt.find_all(["span"])
        details["text"] = _join_texts(span) if list(span) else None

        # General component with no abstract
        g_div = cmpt.find("div", {"class": "g"})
        if g_div:
            parsed_general = parse_general_result(g_div)
            parsed_general = {
                k: v for k, v in parsed_general.items() if k in {"title", "url", "cite"}
            }
            parsed.update(parsed_general)

    elif h2_text == "Unit Converter":
        parsed["sub_type"] = "unit_converter"
        span = cmpt.find_all(["span"])
        details["text"] = _join_texts(span) if list(span) else None

    elif h2_text == "Sports Results":
        parsed["sub_type"] = "sports"
        div = cmpt.find("div", {"class": "SwsxUd"})
        details["text"] = div.text if div else None

    elif h2_text == "Weather Result":
        parsed["sub_type"] = "weather"

    elif h2_text == "Finance Results" or cmpt.find(
        "div", {"id": "knowledge-finance-wholepage__entity-summary"}
    ):
        parsed["sub_type"] = "finance"

    elif cmpt.find("div", {"data-attrid": "DictionaryHeader"}) or (
        (button := cmpt.find("div", {"role": "button"})) and button.text == "Dictionary"
    ):
        parsed["sub_type"] = "dictionary"
        # Modern dictionary panels expose structured data-attrid entries.
        entry = cmpt.find(attrs={"data-attrid": "EntryHeader"})
        if entry:
            # "cis·tern / ˈsistərn / Learn to pronounce" -> "cistern"
            word = entry.get_text(" ", strip=True).split("/")[0].replace("·", "").strip()
            parsed["title"] = word or None
        definitions = [
            text
            for d in cmpt.find_all(attrs={"data-attrid": "SenseDefinition"})
            if (text := d.get_text(" ", strip=True))
        ]
        if definitions:
            parsed["text"] = " | ".join(definitions)
            details["text"] = parsed["text"]
        else:
            # Legacy layout fallback.
            vmod = cmpt.find("div", {"class": "vmod"})
            if vmod:
                details["text"] = vmod.get_text(" ", strip=True).split("Translate")[0]
            else:
                span_first = cmpt.find("span", {"jsslot": ""})
                if span_first:
                    span = span_first.find_all("span")
                    details["text"] = (
                        _join_texts(span).split("Translate")[0] if list(span) else None
                    )

    elif h2_text in ("Translation Result", "Resultado de traducción"):
        parsed["sub_type"] = "translate"
        span = cmpt.find_all("span")
        details["text"] = _join_texts(span).split("Community Verified")[0] if list(span) else None

    elif h2_text == "Calculator Result":
        parsed["sub_type"] = "calculator"

    elif details["heading"] == "2020 US election results":
        parsed["sub_type"] = "election"
        span = cmpt.find_all(["span"])
        details["text"] = _join_texts(span) if list(span) else None

    elif cmpt.find("span", {"role": "heading", "class": "IFnjPb"}):
        heading_span = cmpt.find("span", {"role": "heading", "class": "IFnjPb"})
        if heading_span and heading_span.text.strip() in (
            "Things to know",
            "Cosas que debes saber",
        ):
            parsed["sub_type"] = "things_to_know"
            details["heading"] = heading_span.text.strip()

    elif cmpt.find("div", {"class": "JNkvid"}) and (
        section_heading := cmpt.find(attrs={"role": "heading", "aria-level": "2"})
    ):
        heading_text = section_heading.get_text(" ", strip=True)
        # slugify first (whitespace-robust), then map the literal `&` token.
        parsed["sub_type"] = slugify(heading_text.lower(), sep="-").replace("-&-", "-and-")
        parsed["title"] = heading_text
        # Drop Google KG-navigation /search? links — they're internal entity redirects.
        details["urls"] = [
            u for u in details.get("urls", []) if not u["url"].startswith("/search?")
        ]
        items = [
            h.get_text(" ", strip=True)
            for h in cmpt.find_all(attrs={"role": "heading", "aria-level": "3"})
        ]
        if items:
            details["items"] = items

    else:
        parsed["sub_type"] = "panel"
        # pyrefly: ignore[no-matching-overload]
        div = cmpt.find_all(["span", "div", "a"], string=True)
        details["text"] = _join_texts(div) if list(div) else None

        text_divs = cmpt.find_all("div", {"class": "sinMW"})
        text_list = [t for t in (get_text(div, strip=True) for div in text_divs) if t]
        parsed["text"] = "<|>".join(text_list) if text_list else None
        parsed["title"] = get_text(cmpt, "div", {"class": ["ZbhV9d", "HdbW6"]}, strip=True)

    img_div = cmpt.find("div", {"class": "img-brk"})
    if img_div:
        a = img_div.find("a")
        details["img_url"] = a["href"] if a else None
    else:
        details["img_url"] = None
    details["type"] = "panel"
    parsed["details"] = details

    return [parsed]


def _join_texts(div) -> str:
    return "|".join([d.get_text(separator=" ") for d in div if d.text])


def _first_external_link(node: Node) -> dict | None:
    """Return the first absolute (external) anchor (url + text) within ``node``.

    Skips root-relative Google links (``/search?``, ``/intl/...`` disclaimers,
    etc.) — only ``http(s)://`` targets count.
    """
    for a in node.find_all("a", href=True):
        href = str(a["href"])
        if not href.startswith(("http://", "https://")):
            continue
        return {"url": href, "text": a.get_text(" ", strip=True)}
    return None


def parse_alink(a: Node) -> dict:
    return {"url": a["href"], "text": a.get_text("|")}
