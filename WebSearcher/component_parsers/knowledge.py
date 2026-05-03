"""Parse the Knowledge Box component.

A wide-format panel surfaced on entity / topical queries. Sub_type covers a
large set of variants: AI overview, featured results, featured snippet, unit
converter, sports, weather, finance, dictionary, translation, calculator,
election results, "things to know", and the generic panel layout.
"""

import bs4

from .. import utils
from .general import parse_general_result


def parse_knowledge_panel(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list:
    parsed: dict = {"type": "knowledge", "sub_rank": sub_rank}

    # Get embedded result if it exists
    result = cmpt.find("div", {"class": "rc"})
    if result:
        parsed["title"] = utils.get_text(result, "h3")
        parsed["url"] = utils.get_link(result)
        parsed["cite"] = utils.get_text(result, "cite")

    parsed["text"] = utils.get_text(cmpt, "div", {"role": "heading", "aria-level": "3"})

    details: dict = {}

    heading = cmpt.find("div", {"role": "heading"})
    details["heading"] = heading.text if heading else None

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

    if cmpt.find("div", {"class": "Fzsovc"}):
        parsed["sub_type"] = "ai_overview"
    elif cmpt.find("div", {"class": "pxiwBd"}):
        parsed["sub_type"] = "featured_results"
    elif h2_text == "Featured snippet from the web" or cmpt.find(
        "div", {"class": "answered-question"}
    ):
        parsed["sub_type"] = "featured_snippet"
        span = cmpt.find_all(["span"])
        details["text"] = get_text(span) if list(span) else None

        # General component with no abstract
        g_div = cmpt.find("div", {"class": "g"})
        if isinstance(g_div, bs4.element.Tag):
            parsed_general = parse_general_result(g_div)
            parsed_general = {
                k: v for k, v in parsed_general.items() if k in {"title", "url", "cite"}
            }
            parsed.update(parsed_general)

    elif h2_text == "Unit Converter":
        parsed["sub_type"] = "unit_converter"
        span = cmpt.find_all(["span"])
        details["text"] = get_text(span) if list(span) else None

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
        vmod = cmpt.find("div", {"class": "vmod"})
        if vmod:
            details["text"] = vmod.get_text(" ", strip=True).split("Translate")[0]
        else:
            span_first = cmpt.find("span", {"jsslot": ""})
            if span_first:
                span = span_first.find_all("span")
                details["text"] = get_text(span).split("Translate")[0] if list(span) else None

    elif h2_text in ("Translation Result", "Resultado de traducción"):
        parsed["sub_type"] = "translate"
        span = cmpt.find_all("span")
        details["text"] = get_text(span).split("Community Verified")[0] if list(span) else None

    elif h2_text == "Calculator Result":
        parsed["sub_type"] = "calculator"

    elif details["heading"] == "2020 US election results":
        parsed["sub_type"] = "election"
        span = cmpt.find_all(["span"])
        details["text"] = get_text(span) if list(span) else None

    elif cmpt.find("span", {"role": "heading", "class": "IFnjPb"}):
        heading_span = cmpt.find("span", {"role": "heading", "class": "IFnjPb"})
        if heading_span and heading_span.text.strip() in (
            "Things to know",
            "Cosas que debes saber",
        ):
            parsed["sub_type"] = "things_to_know"
            details["heading"] = heading_span.text.strip()

    else:
        parsed["sub_type"] = "panel"
        # pyrefly: ignore[no-matching-overload]
        div = cmpt.find_all(["span", "div", "a"], string=True)
        details["text"] = get_text(div) if list(div) else None

        text_divs = cmpt.find_all("div", {"class": "sinMW"})
        text_list = [t for t in (utils.get_text(div) for div in text_divs) if t]
        parsed["text"] = "<|>".join(text_list) if text_list else None
        parsed["title"] = utils.get_text(cmpt, "div", {"class": ["ZbhV9d", "HdbW6"]})

    img_div = cmpt.find("div", {"class": "img-brk"})
    if img_div:
        a = img_div.find("a")
        details["img_url"] = a["href"] if a else None
    else:
        details["img_url"] = None
    details["type"] = "panel"
    parsed["details"] = details

    return [parsed]


def get_text(div) -> str:
    return "|".join([d.get_text(separator=" ") for d in div if d.text])


def parse_alink(a: bs4.element.Tag) -> dict:
    return {"url": a["href"], "text": a.get_text("|")}
