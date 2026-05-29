"""Parse a Twitter single-result component.

Visually similar to a general result but linking to a Twitter account, with
a tweet sometimes embedded in the snippet.
"""

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text


def parse_twitter_result(cmpt, sub_rank: int = 0) -> list:
    node: Node = cmpt
    parsed: dict = {"type": "twitter_result", "sub_rank": sub_rank}

    header = node.css_first("div.DOqJne")
    if header is not None:
        title = header.css_first("g-link")
        if title is not None:
            anchor = title.css_first("a")
            if anchor is not None:
                parsed["title"] = get_text(anchor)
                parsed["url"] = anchor.attributes["href"]

        cite = header.css_first("cite")
        if cite is not None:
            parsed["cite"] = get_text(cite)

    tw_res = node.css_first("div.tw-res")
    if tw_res is not None:
        # bs4 .children yielded direct children (Tags + NavigableStrings). The
        # original destructured `body, timestamp_url = tw_res.children` and
        # guarded with is_tag, so element-only iteration matches what was kept.
        elems = list(tw_res.iter(include_text=False))
        if len(elems) >= 2:
            body, timestamp_url = elems[0], elems[1]
            parsed["text"] = get_text(body)
            parsed["timestamp"] = get_text(timestamp_url.css_first("span"))
            a = timestamp_url.css_first("a")
            tweet_url = a.attributes.get("href") if a is not None else None
            parsed["details"] = {"type": "tweet", "url": tweet_url} if tweet_url else None
    return [parsed]
