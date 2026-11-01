"""Parse a "Top Stories" component.

These components contain links to news articles and often feature an image.
Sometimes the subcomponents are stacked vertically, and sometimes they are
stacked horizontally and feature a larger image, resembling the video
component. Also backs the perspectives, latest_from, local_news and
recent_posts parsers via the ``ctype`` argument.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import class_tokens, get_text, has_text, is_element
from ...models.data import ERR_NO_SUBCOMPONENTS, error_details
from ._common import mark_hidden_row, mark_timestamp_row
from ._deferred_html import fill_deferred_html
from ._video_card import parse_evlb_card


def parse_top_stories(elem: Node, ctype: str = "top_stories") -> list[dict[str, Any]]:
    node: Node = elem
    # Cards past the first few, and those in collapsed topics, are deferred.
    fill_deferred_html(node)
    divs: list[Node] = []
    divs.extend(d for d in node.css("g-inner-card") if has_text(d))  # Top Stories
    # find_children equivalent: direct element children of div.qmv19b (no empty
    # filter). iter(include_text=False) still yields comment/CDATA nodes, which
    # would parse into all-None rows and shift every later sub_rank.
    container = node.css_first("div.qmv19b")
    if container is not None:
        divs.extend(c for c in container.iter(include_text=False) if is_element(c))
    divs.extend(d for d in node.css("div.IJl0Z") if has_text(d))  # Top Stories
    divs.extend(d for d in node.css("div.JJZKK") if has_text(d))  # Perspectives

    # Modern Perspectives: every carousel item is role=listitem (covers both
    # standard cards and embedded tweets, including AI-themed sub-carousels).
    # Cards not yet loaded at capture are empty placeholders with no text and no
    # link; data-init-vis="false" is no signal, loaded cards carry it too. A
    # carousel of placeholders only stops here, as the error row, rather than
    # reaching the fallbacks below.
    listitems: list[Node] = [] if divs else node.css('[role="listitem"]')
    divs.extend(d for d in listitems if has_text(d) or d.css_first("a[href]") is not None)

    if not divs and not listitems:
        # 2026-10 Top Stories (g-section-with-header.yG4QQe): every story card is
        # an a.aJWbwf, in the vertical list and in the div.MmyPhf clusters alike.
        divs.extend(d for d in node.css("a.aJWbwf") if has_text(d))

    if not divs and not listitems:
        # Older Top Stories vertical layout
        link_divs = [d for d in node.css("a.WlydOe") if has_text(d)]
        divs.extend([div.parent for div in link_divs if div.parent is not None])

    # The selectors above overlap (a qmv19b child can itself be a g-inner-card),
    # so keep the first occurrence of each node in document order.
    seen: set[int] = set()
    divs = [d for d in divs if not (d.mem_id in seen or seen.add(d.mem_id))]

    if divs:
        topics = _topics_by_panel(node)
        return [
            _mark_topic(parse_top_story(div, ctype, i), div, topics) for i, div in enumerate(divs)
        ]
    return [{"type": ctype, "sub_rank": 0, "details": error_details(ERR_NO_SUBCOMPONENTS)}]


def _row_details(parsed: dict[str, Any]) -> dict[str, Any]:
    """The row's ``details``, created as a metadata-only ``item`` when it has none."""
    details = parsed.get("details")
    if isinstance(details, dict):
        return details
    details = {"type": "item"}
    parsed["details"] = details
    return details


def _topics_by_panel(node: Node) -> dict[int, str]:
    """Label of each collapsible topic, keyed by the ``mem_id`` of the panel it opens."""
    topics: dict[int, str] = {}
    for button in node.css('[role="button"][aria-expanded][aria-controls]'):
        panel = node.css_first(f'[id="{button.attrs["aria-controls"]}"]')
        label = get_text(button.css_first("span"), " ", strip=True)
        if panel is not None and label:
            topics[panel.mem_id] = label
    return topics


def _mark_topic(parsed: dict[str, Any], sub: Node, topics: dict[int, str]) -> dict[str, Any]:
    """Record the collapsible topic a card sits under, if any, in ``details``."""
    parent = sub.parent
    while topics and parent is not None:
        if label := topics.get(parent.mem_id):
            _row_details(parsed)["topic"] = label
            break
        parent = parent.parent
    return parsed


def parse_top_story(sub: Node, ctype: str, sub_rank: int = 0) -> dict[str, Any]:
    title = None
    for sel in ("div.n0jPhd", "div.eAaXgc", "div.xcQxib"):
        t = get_text(sub.css_first(sel), " ")
        if t:
            title = t
            break
    a = sub.css_first("a")
    url = a.attrs.get("href") if a is not None else None
    parsed: dict[str, Any] = {
        "type": ctype,
        "sub_rank": sub_rank,
        "title": title,
        "url": url,
        "text": get_text(sub.css_first("div.GI74Re"), " "),
        "cite": get_cite(sub),
    }
    # YouTube items (frequent in perspectives) carry a hidden evlb_* card.
    # Content details first, so the visible flag rides as a sibling key.
    fields = parse_evlb_card(sub)
    if fields:
        parsed["details"] = {"type": "video", **fields}
    # 2026-10 cards carry the story's age ("8 hours ago") as the last child span
    # of div.OSrXXb, after an optional "Video" label (span.Uz7khf).
    age = sub.css_first("div.OSrXXb")
    if age is not None:
        spans = [
            c
            for c in age.iter(include_text=False)
            if is_element(c) and c.tag == "span" and "Uz7khf" not in class_tokens(c)
        ]
        mark_timestamp_row(parsed, get_text(spans[-1], " ", strip=True) if spans else None)
    # Embedded posts carry the age in a span[data-ts] and link their author apart
    # from the post.
    mark_timestamp_row(parsed, get_text(sub.css_first("span[data-ts]"), " ", strip=True))
    author = sub.css_first('div[id^="twitter_attribution"] a[href]')
    if author is not None:
        _row_details(parsed)["author_url"] = author.attrs.get("href")
    return mark_hidden_row(parsed, sub)


def get_cite(sub: Node) -> str | None:
    div_cite = sub.css_first("div.Dx69l")  # Perspectives
    if div_cite is not None:
        return get_text(div_cite, " ")

    tweet_cite = sub.css_first("div.Du2Vwd")  # Perspectives - embedded tweet
    if tweet_cite is not None:
        return get_text(tweet_cite, " ")

    attribution = sub.css_first("atx-attribution div.sTl1Td")  # 2026-10 Perspectives
    if attribution is not None:
        return get_text(attribution, " ", strip=True)

    author = get_text(sub.css_first("div.R8BTeb"), " ", strip=True)  # 2026-10 Recent posts
    if author:
        platform = get_text(sub.css_first("div.xuPcX"), " ", strip=True)
        return f"{author} · {platform}" if platform else author

    img_cite = sub.css_first("g-img.sL0zmc")  # Top Stories - image cite
    if img_cite is not None:
        img = img_cite.css_first("img")
        alt = img.attrs.get("alt") if img is not None else None
        return str(alt) if alt else None

    if sub.css_first("g-img.QyR1Ze") is not None:
        return get_text(sub.css_first("span"), " ")

    source = sub.css_first("div.MgUUmf")  # Top Stories - 2026-10 source name
    if source is not None:
        return get_text(source, " ")
    return get_text(sub.css_first("cite"), " ")
