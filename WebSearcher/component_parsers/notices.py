"""Parse a query-notice component.

Notices Google adds at the top of results: query edits ("Showing results
for"), suggestions ("Did you mean"), location prompts ("Choose area" /
"Use precise location"), and language tips. Each variant is dispatched to
its own handler based on visible text.
"""

import re
from collections.abc import Callable

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text, reparse_fragment

# Visible-text markers that identify each notice sub-type. ``location_*`` and
# ``language_*`` require every marker present; ``query_*`` matches on any.
_SUB_TYPE_TEXT: dict[str, set[str]] = {
    "query_edit": {"Showing results for", "Including results for"},
    "query_edit_no_results": {"No results found for"},
    "query_suggestion": {
        "Did you mean:",
        "Are you looking for:",
        "Search for this instead?",
        "Did you mean to search for:",
        "Search instead for:",
    },
    "location_choose_area": {"Results for", "Choose area"},
    "location_use_precise_location": {"Results for", "Use precise location"},
    "language_tip": {"Tip:", "Learn more about filtering by language"},
}


def parse_notices(elem) -> list:
    node: Node = elem
    sub_type = _classify_sub_type(node)
    sub_parser = _SUB_TYPE_PARSERS.get(sub_type)
    parsed = sub_parser(node) if sub_parser else {}
    return [
        {
            "type": "notice",
            "sub_type": sub_type,
            "sub_rank": 0,
            "title": parsed.get("title"),
            "text": parsed.get("text"),
        }
    ]


def _classify_sub_type(node: Node) -> str:
    cmpt_text = re.sub(r"\s+", " ", (get_text(node) or "").strip())
    for sub_type, text_list in _SUB_TYPE_TEXT.items():
        if sub_type.startswith("query_"):
            if any(text in cmpt_text for text in text_list):
                return sub_type
        elif all(text in cmpt_text for text in text_list):  # location_* / language_*
            return sub_type
    return "unknown"


def _parse_no_results_replacement(node: Node) -> dict:
    output: dict[str, str | None] = {"title": None, "text": None}

    # bs4 ``copy.copy(node)`` cloned the subtree so the subsequent
    # ``div_title.extract()`` didn't mutate the live tree. selectolax has no
    # copy.copy; reparse the node's html into an independent tree.
    clone = reparse_fragment(node)
    div_title = clone.css_first('div[role="heading"][aria-level="2"]')
    if div_title is not None:
        output["title"] = (get_text(div_title) or "").strip()
        div_title.remove(recursive=False)

    div_text = clone.css_first("div.card-section")
    if div_text is not None:
        output["text"] = (get_text(div_text) or "").strip()

    return output


def _parse_query_edit(node: Node) -> dict:
    title = get_text(node.css_first("span.gL9Hy"), " ", strip=True)
    modified = get_text(node.css_first("a#fprsl"), " ", strip=True)
    if title and modified:
        title = f"{title} {modified}"

    text = get_text(node.css_first("span.spell_orig"), " ", strip=True)
    original = get_text(node.css_first("a.spell_orig"), " ", strip=True)
    if text and original:
        text = f"{text} {original}"

    return {"title": title, "text": text}


def _parse_query_suggestion(node: Node) -> dict:
    title = None
    for name in ("span", "div"):
        title = get_text(node.css_first(f"{name}.gL9Hy"), " ", strip=True)
        if title:
            break

    links = list(node.css("a.gL9Hy"))
    suggestions = [t for t in (get_text(s) for s in links if s is not None) if t]
    return {"title": title, "text": "<|>".join(suggestions)}


def _parse_location_heading(node: Node) -> dict:
    heading = node.css_first("div.eKPi4")
    if heading is None:
        return {"title": None, "text": None}
    results_for = get_text(heading.css_first("span.gm7Ysb"), " ", strip=True)
    location = get_text(heading.css_first("span.BBwThe"), " ", strip=True)
    title = f"{results_for} {location}" if results_for and location else None
    return {"title": title, "text": None}


def _parse_language_tip(node: Node) -> dict:
    title = get_text(node.css_first("div.Ww4FFb"), " ")
    return {
        "title": re.sub(r"\s+", " ", title) if title else None,
        "text": None,
    }


# type-name -> handler. Built once at import; ``location_*`` share a handler.
_SUB_TYPE_PARSERS: dict[str, Callable[[Node], dict]] = {
    "query_edit": _parse_query_edit,
    "query_edit_no_results": _parse_no_results_replacement,
    "query_suggestion": _parse_query_suggestion,
    "location_choose_area": _parse_location_heading,
    "location_use_precise_location": _parse_location_heading,
    "language_tip": _parse_language_tip,
}
