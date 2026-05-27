"""Parse a Twitter single-result component.

Visually similar to a general result but linking to a Twitter account, with
a tweet sometimes embedded in the snippet.
"""

import bs4

from .._slx import is_tag
from ..utils import get_link, get_text


def parse_twitter_result(cmpt: bs4.element.Tag, sub_rank: int = 0) -> list:
    parsed: dict = {"type": "twitter_result", "sub_rank": sub_rank}

    header = cmpt.find("div", {"class": "DOqJne"})
    if header:
        title = header.find("g-link")
        if title:
            anchor = title.find("a")
            if anchor:
                parsed["title"] = anchor.text
                parsed["url"] = anchor["href"]

        cite = header.find("cite")
        if cite:
            parsed["cite"] = cite.text

    tw_res = cmpt.find("div", {"class": "tw-res"})
    if tw_res:
        body, timestamp_url = tw_res.children
        if is_tag(body):
            parsed["text"] = get_text(body)
        if is_tag(timestamp_url):
            parsed["timestamp"] = get_text(timestamp_url, "span")
            tweet_url = get_link(timestamp_url)
            parsed["details"] = {"type": "tweet", "url": tweet_url} if tweet_url else None
    return [parsed]
