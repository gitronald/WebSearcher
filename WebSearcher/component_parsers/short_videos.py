"""Parse a "Short videos" carousel component.

A horizontal carousel of short-form video cards (YouTube Shorts, TikTok, etc.)
with a heading, source, and duration.
"""

from selectolax.parser import Node

from .._slx import get_text


def parse_short_videos(cmpt) -> list:
    node: Node = cmpt.raw
    # Filter to full card links (with heading), skip thumbnail-only duplicates.
    cards = [a for a in node.css("a.rIRoqf") if a.css_first('div[role="heading"]') is not None]
    if not cards:
        return [{"type": "short_videos", "sub_rank": 0}]

    parsed_list = []
    for i, card in enumerate(cards):
        parsed = {
            "type": "short_videos",
            "sub_rank": i,
            "url": card.attributes.get("href"),
            "title": get_text(card.css_first('div[role="heading"]'), " "),
        }

        # Source (YouTube, TikTok, etc.) and duration
        cite = get_text(card.css_first("span.xFMKFe"), " ")
        if cite:
            parsed["cite"] = cite

        parsed_list.append(parsed)

    return parsed_list
