"""Parse a query-notice component.

Notices Google adds at the top of results: query edits ("Showing results
for"), suggestions ("Did you mean"), location prompts ("Choose area" /
"Use precise location"), and language tips. Each variant is dispatched to
its own handler based on visible text.
"""

import re
from collections.abc import Callable

from selectolax.parser import Node

from .._slx import get_text, reparse_fragment


def parse_notices(cmpt) -> list:
    return NoticeParser().parse_notices(cmpt)


class NoticeParser:
    def __init__(self):
        self.parsed: dict = {}
        self.sub_type: str = "unknown"
        self.parsed_list: list = []
        self.sub_type_text: dict[str, set[str]] = {
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
        self.parser_dict: dict[str, Callable[[Node], dict]] = {
            "query_edit": self._parse_query_edit,
            "query_edit_no_results": self._parse_no_results_replacement,
            "query_suggestion": self._parse_query_suggestion,
            "location_choose_area": self._parse_location_heading,
            "location_use_precise_location": self._parse_location_heading,
            "language_tip": self._parse_language_tip,
        }

    def parse_notices(self, cmpt) -> list:
        node: Node = cmpt.raw if hasattr(cmpt, "raw") else cmpt
        self._classify_sub_type(node)
        self._parse_sub_type(node)
        self._package_parsed()
        return self.parsed_list

    def _classify_sub_type(self, node: Node) -> None:
        cmpt_text = re.sub(r"\s+", " ", (get_text(node) or "").strip())

        for sub_type, text_list in self.sub_type_text.items():
            if sub_type.startswith("location_"):
                if all(text in cmpt_text for text in text_list):
                    self.sub_type = sub_type
                    break
            elif sub_type.startswith("query_"):
                if any(text in cmpt_text for text in text_list):
                    self.sub_type = sub_type
                    break
            elif sub_type.startswith("language_"):
                if all(text in cmpt_text for text in text_list):
                    self.sub_type = sub_type
                    break

    def _parse_sub_type(self, node: Node) -> None:
        sub_parser = self.parser_dict.get(self.sub_type, None)
        if sub_parser:
            self.parsed = sub_parser(node)

    def _package_parsed(self) -> None:
        self.parsed_list = [
            {
                "type": "notice",
                "sub_type": self.sub_type,
                "sub_rank": 0,
                "title": self.parsed.get("title", None),
                "text": self.parsed.get("text", None),
            }
        ]

    def _parse_no_results_replacement(self, node: Node) -> dict:
        output: dict[str, str | None] = {"title": None, "text": None}

        # bs4 ``copy.copy(cmpt)`` clones the subtree so the subsequent
        # ``div_title.extract()`` doesn't mutate the live tree. selectolax has
        # no copy.copy; reparse the node's html into an independent tree.
        clone = reparse_fragment(node)
        div_title = clone.css_first('div[role="heading"][aria-level="2"]')
        if div_title is not None:
            output["title"] = (get_text(div_title) or "").strip()
            div_title.remove(recursive=False)

        div_text = clone.css_first("div.card-section")
        if div_text is not None:
            output["text"] = (get_text(div_text) or "").strip()

        return output

    def _parse_query_edit(self, node: Node) -> dict:
        title = get_text(node.css_first("span.gL9Hy"), " ", strip=True)
        modified = get_text(node.css_first("a#fprsl"), " ", strip=True)
        if title and modified:
            title = f"{title} {modified}"

        text = get_text(node.css_first("span.spell_orig"), " ", strip=True)
        original = get_text(node.css_first("a.spell_orig"), " ", strip=True)
        if text and original:
            text = f"{text} {original}"

        return {"title": title, "text": text}

    def _parse_query_suggestion(self, node: Node) -> dict:
        title = None
        for name in ("span", "div"):
            title = get_text(node.css_first(f"{name}.gL9Hy"), " ", strip=True)
            if title:
                break

        links = list(node.css("a.gL9Hy"))
        suggestions = [t for t in (get_text(s) for s in links if s is not None) if t]
        return {"title": title, "text": "<|>".join(suggestions)}

    def _parse_location_heading(self, node: Node) -> dict:
        heading = node.css_first("div.eKPi4")
        if heading is None:
            return {"title": None, "text": None}
        results_for = get_text(heading.css_first("span.gm7Ysb"), " ", strip=True)
        location = get_text(heading.css_first("span.BBwThe"), " ", strip=True)
        title = f"{results_for} {location}" if results_for and location else None
        return {"title": title, "text": None}

    def _parse_language_tip(self, node: Node) -> dict:
        title = get_text(node.css_first("div.Ww4FFb"), " ")
        return {
            "title": re.sub(r"\s+", " ", title) if title else None,
            "text": None,
        }
