"""Parse a "Short videos" carousel component.

A horizontal carousel of short-form video cards (YouTube Shorts, TikTok, etc.)
with a heading, source, and duration.
"""

from selectolax.parser import Node

from ..utils import get_text


def parse_short_videos(cmpt: Node) -> list:
    # Filter to full card links (with heading), skip thumbnail-only duplicates
    cards = [
        a for a in cmpt.find_all("a", {"class": "rIRoqf"}) if a.find("div", {"role": "heading"})
    ]
    if not cards:
        return [{"type": "short_videos", "sub_rank": 0}]

    parsed_list = []
    for i, card in enumerate(cards):
        parsed = {
            "type": "short_videos",
            "sub_rank": i,
            "url": card.get("href"),
            "title": get_text(card, "div", {"role": "heading"}),
        }

        # Source (YouTube, TikTok, etc.) and duration
        cite = get_text(card, "span", {"class": "xFMKFe"})
        if cite:
            parsed["cite"] = cite

        parsed_list.append(parsed)

    return parsed_list
