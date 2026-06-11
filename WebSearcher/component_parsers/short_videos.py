"""Parse a "Short videos" carousel component.

A horizontal carousel of short-form video cards (YouTube Shorts, TikTok, etc.)
with a heading, source, and duration.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text
from ._common import mark_hidden_row
from ._video_card import evlb_fields_by_tile


def parse_short_videos(elem) -> list:
    node: Node = elem
    # Filter to full card links (with heading), skip thumbnail-only duplicates.
    cards = [a for a in node.css("a.rIRoqf") if a.css_first('div[role="heading"]') is not None]
    if not cards:
        return [{"type": "short_videos", "sub_rank": 0}]

    # The hidden evlb_* card sits beside each anchor in a per-video wrapper,
    # not inside it -- map wrappers to anchors within this component only.
    fields_by_tile = evlb_fields_by_tile(node, cards)

    parsed_list = []
    for i, card in enumerate(cards):
        parsed: dict = {
            "type": "short_videos",
            "sub_rank": i,
            "url": card.attributes.get("href"),
            "title": get_text(card.css_first('div[role="heading"]'), " "),
        }

        # Source (YouTube, TikTok, etc.) and duration
        cite = get_text(card.css_first("span.xFMKFe"), " ")
        if cite:
            parsed["cite"] = cite

        # Content details first, so the visible flag rides as a sibling key.
        fields = fields_by_tile.get(card.mem_id)
        if fields:
            parsed["details"] = {"type": "video", **fields}

        parsed_list.append(mark_hidden_row(parsed, card))

    return parsed_list
