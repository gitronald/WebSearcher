"""Parse a "Discussions and forums" component.

A list of forum/discussion threads (Reddit, Stack Overflow, etc.) with title,
source, and link. Each row has multiple known card layouts.
"""

from selectolax.parser import Node

from .._slx import get_text


def parse_discussions_and_forums(cmpt) -> list:
    node: Node = cmpt.raw
    for sel in ("div.LJ7wUe", "div.JlqpRe", "div.EDblX"):
        subs = node.css(sel)
        if subs:
            return [parse_item(sub, sub_rank) for sub_rank, sub in enumerate(subs)]
    return []


def parse_item(cmpt: Node, sub_rank: int = 0) -> dict:
    return {
        "type": "discussions_and_forums",
        "sub_type": None,
        "sub_rank": sub_rank,
        "title": get_title(cmpt),
        "url": get_url(cmpt),
        "cite": get_cite(cmpt),
    }


def get_title(sub: Node) -> str | None:
    for sel in ("div.zNWc4c", "div.qyp6xb"):
        text = get_text(sub.css_first(sel), " ")
        if text:
            return text
    return get_text(sub.css_first('div[role="heading"]'), " ")


def get_cite(sub: Node) -> str | None:
    for sel in ("div.LbKnXb", "div.VZGVuc"):
        text = get_text(sub.css_first(sel), " ")
        if text:
            return text
    return None


def get_url(sub: Node) -> str | None:
    # Prefer the publisher anchor if present, fall back to the first anchor.
    for sel in ("a.v4kUNc", "a"):
        a = sub.css_first(sel)
        href = a.attributes.get("href") if a is not None else None
        if href:
            return href
    return None
