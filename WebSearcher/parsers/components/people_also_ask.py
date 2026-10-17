"""Parse a "People Also Ask" component.

A list of questions whose answers are revealed via expand-on-click. Browser
automation is required to capture most of the dropdown content; this parser
captures the question text.

In the 2026-10 layout the first question often ships its generated answer
already expanded, in the role-heading AI overview markup (``div.mZJni``). That
answer is parsed into ``details["answer"]`` with the main overview's fields,
and the row's ``sub_type`` is ``ai_overview``.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import get_text
from .ai_overview import extract_overview


def parse_people_also_ask(elem: Node, sub_rank: int = 0) -> list[dict[str, Any]]:
    node: Node = elem
    questions = node.css("div.related-question-pair")
    parsed_questions = list(filter(None, (parse_question(q) for q in questions)))
    # Read the answer after the questions: it decomposes citation widgets.
    answer = parse_answer(questions)
    details: dict[str, Any] | None = None
    if parsed_questions or answer:
        details = {"type": "text", "items": parsed_questions}
        if answer:
            details["answer"] = answer
    parsed: dict[str, Any] = {
        "type": "people_also_ask",
        "sub_type": "ai_overview" if answer else None,
        "sub_rank": sub_rank,
        "text": "<|>".join(parsed_questions) if parsed_questions else None,
        "details": details,
    }
    return [parsed]


def parse_question(question: Node) -> str | None:
    for sel in ("div.rc", "div.yuRUbf", "div.iDjcJe", "div.JlqpRe", "div.cbphWd"):
        text = get_text(question.css_first(sel), " ", strip=True)
        if text:
            return text
    return None


def parse_answer(questions: list[Node]) -> dict[str, Any] | None:
    """The generated answer shipped expanded under a question, or None.

    Source cards are scoped to the question holding the answer. Only the first
    answer is kept: every PAA seen so far carries at most one, under its first
    question.
    """
    for question in questions:
        content = question.css_first("div.mZJni")
        if content is None:
            continue
        overview = extract_overview(content, question)
        if overview["text"] is None and "sections" not in overview:
            continue
        return {"question": question.attributes.get("data-q") or None, **overview}
    return None
