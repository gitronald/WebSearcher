"""Parse a query-notice component.

Notices Google adds at the top of results: query edits ("Showing results
for"), suggestions ("Did you mean"), location prompts ("Choose area" /
"Use precise location"), and language tips. Each variant is dispatched to
its own handler based on visible text.
"""

import copy
import re
from collections.abc import Callable

import bs4

from ..utils import get_text


def parse_notices(cmpt: bs4.element.Tag) -> list:
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
        self.parser_dict: dict[str, Callable[[bs4.element.Tag], dict]] = {
            "query_edit": self._parse_query_edit,
            "query_edit_no_results": self._parse_no_results_replacement,
            "query_suggestion": self._parse_query_suggestion,
            "location_choose_area": self._parse_location_heading,
            "location_use_precise_location": self._parse_location_heading,
            "language_tip": self._parse_language_tip,
        }

    def parse_notices(self, cmpt: bs4.element.Tag) -> list:
        self._classify_sub_type(cmpt)
        self._parse_sub_type(cmpt)
        self._package_parsed()
        return self.parsed_list

    def _classify_sub_type(self, cmpt: bs4.element.Tag) -> None:
        cmpt_text = re.sub(r"\s+", " ", cmpt.text.strip())

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

    def _parse_sub_type(self, cmpt: bs4.element.Tag) -> None:
        sub_parser = self.parser_dict.get(self.sub_type, None)
        if sub_parser:
            self.parsed = sub_parser(cmpt)

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

    def _parse_no_results_replacement(self, cmpt: bs4.element.Tag) -> dict:
        output: dict[str, str | None] = {"title": None, "text": None}

        cmpt = copy.copy(cmpt)
        div_title = cmpt.find("div", {"role": "heading", "aria-level": "2"})
        if div_title:
            output["title"] = div_title.text.strip()
            div_title.extract()

        div_text = cmpt.find("div", {"class": "card-section"})
        if div_text:
            output["text"] = div_text.text.strip()

        return output

    def _parse_query_edit(self, cmpt: bs4.element.Tag) -> dict:
        title = get_text(cmpt, "span", {"class": "gL9Hy"}, strip=True)
        modified = get_text(cmpt, "a", {"id": "fprsl"}, strip=True)
        if title and modified:
            title = f"{title} {modified}"

        text = get_text(cmpt, "span", {"class": "spell_orig"}, strip=True)
        original = get_text(cmpt, "a", {"class": "spell_orig"}, strip=True)
        if text and original:
            text = f"{text} {original}"

        return {"title": title, "text": text}

    def _parse_query_suggestion(self, cmpt: bs4.element.Tag) -> dict:
        title = None
        for name in ("span", "div"):
            title = get_text(cmpt, name, {"class": "gL9Hy"}, strip=True)
            if title:
                break

        links = cmpt.find_all("a", class_="gL9Hy")
        suggestions = [t for t in (get_text(s) for s in links if s) if t]
        return {"title": title, "text": "<|>".join(suggestions)}

    def _parse_location_heading(self, cmpt: bs4.element.Tag) -> dict:
        heading = cmpt.find("div", class_="eKPi4")
        if not heading:
            return {"title": None, "text": None}
        results_for = get_text(heading, "span", {"class": "gm7Ysb"}, strip=True)
        location = get_text(heading, "span", {"class": "BBwThe"}, strip=True)
        title = f"{results_for} {location}" if results_for and location else None
        return {"title": title, "text": None}

    def _parse_language_tip(self, cmpt: bs4.element.Tag) -> dict:
        title = get_text(cmpt, "div", {"class": "Ww4FFb"})
        return {
            "title": re.sub(r"\s+", " ", title) if title else None,
            "text": None,
        }
