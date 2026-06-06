"""Parse a "People Also Ask" component.

A list of questions whose answers are revealed via expand-on-click. Browser
automation is required to capture the dropdown content; this parser only
captures the question text.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text


def parse_people_also_ask(elem, sub_rank: int = 0) -> list:
    node: Node = elem
    questions = node.css("div.related-question-pair")
    parsed_questions = list(filter(None, (parse_question(q) for q in questions)))
    parsed: dict = {
        "type": "people_also_ask",
        "sub_rank": sub_rank,
        "text": "<|>".join(parsed_questions) if parsed_questions else None,
        "details": {"type": "text", "items": parsed_questions} if parsed_questions else None,
    }
    return [parsed]


def parse_question(question: Node) -> str | None:
    for sel in ("div.rc", "div.yuRUbf", "div.iDjcJe", "div.JlqpRe", "div.cbphWd"):
        text = get_text(question.css_first(sel), " ", strip=True)
        if text:
            return text
    return None
