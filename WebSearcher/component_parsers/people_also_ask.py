"""Parse a "People Also Ask" component.

A list of questions whose answers are revealed via expand-on-click. Browser
automation is required to capture the dropdown content; this parser only
captures the question text.
"""

import bs4

from ..utils import Selector, get_text_by_selectors


def parse_people_also_ask(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list:
    questions = cmpt.find_all("div", {"class": "related-question-pair"})
    parsed_questions = [parse_question(q) for q in questions]
    parsed_questions = list(filter(None, parsed_questions))
    parsed: dict = {
        "type": "people_also_ask",
        "sub_rank": sub_rank,
        "text": "<|>".join(parsed_questions) if parsed_questions else None,
        "details": {"type": "text", "items": parsed_questions} if parsed_questions else None,
    }
    return [parsed]


def parse_question(question: bs4.element.Tag) -> str | None:
    question_selectors = [
        Selector("div", {"class": "rc"}),
        Selector("div", {"class": "yuRUbf"}),
        Selector("div", {"class": "iDjcJe"}),  # 2023-01-01
        Selector("div", {"class": "JlqpRe"}),  # 2023-11-16
        Selector("div", {"class": "cbphWd"}),  # 2021-01-09
    ]
    return get_text_by_selectors(question, question_selectors, strip=True)
