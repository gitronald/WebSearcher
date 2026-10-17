"""Parse a "General" results component.

The ubiquitous blue-title / green-citation / black-summary results, sometimes
grouped into multi-result components with related themes. Subtypes include
submenus (rating, list, table, mini), scholarly results, products, and videos.
"""

import re
from typing import Any

from selectolax.lexbor import LexborNode as Node

from ..._slx import class_tokens, get_text, next_sibling, subtree_css, subtree_first
from ._common import parse_alink_list
from ._video_card import parse_evlb_card


def parse_general_results(elem: Node) -> list[dict[str, Any]]:
    node: Node = elem
    subs = find_subcomponents(node)
    return [parse_general_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def find_subcomponents(node: Node) -> list[Node]:
    # Standard format -- descendants only, so a wrapping div.g doesn't match itself.
    subs = subtree_css(node, "div.g")
    if subs:
        parent_g = subs[0]  # first .g in document order
        # Nested .g dedup: if parent_g itself contains another .g descendant,
        # return only the outer wrapper.
        if subtree_first(parent_g, "div.g") is not None:
            subs = [parent_g]
        # Host-group sub-results (div.d4rhi) can nest *inside* a div.g main result
        # (2023+ "second result from the same host", stacked/indented under it).
        # Each is a full organic result, but this branch used to return before the
        # d4rhi branch below, silently dropping them. Append any d4rhi in the node
        # so parse_general_results enumerates them (sub_rank 1, 2, ...); the main
        # div.g parses only its own title/cite/snippet via first-match selection,
        # so each nested d4rhi is emitted exactly once as its own indented result.
        return subs + subtree_css(node, "div.d4rhi")

    # Sub-results format (2023+) -- d4rhi host-group with no div.g wrapper
    additional = subtree_css(node, "div.d4rhi")
    if additional:
        first = subtree_first(node, "div")
        return [first] + additional if first is not None else additional

    # Video results
    subs = subtree_css(node, "div.PmEWq")
    if subs:
        return subs

    # Bare organics: several div.tF2Cxc with no div.g wrapper (e.g. a finance /
    # airfares kp-wholepage tab groups multiple organics in one container). Split
    # into one result per tF2Cxc so they are not collapsed into a single result.
    # People-Also-Ask sources (a tF2Cxc inside div.related-question-pair) are not
    # organics and are excluded. Gated to the multi-tF2Cxc case so single-result
    # blocks keep the whole-node fallback below.
    tfs = [n for n in subtree_css(node, "div.tF2Cxc") if not _in_paa_source(n, node)]
    if len(tfs) > 1:
        return tfs

    # Fallback: treat entire component as single result
    return [node]


def _in_paa_source(sub: Node, root: Node) -> bool:
    """True if ``sub`` sits inside a People-Also-Ask ``div.related-question-pair``
    within ``root`` -- a PAA answer source, not an organic result."""
    node = sub.parent
    while node is not None and node.mem_id != root.mem_id:
        if "related-question-pair" in class_tokens(node):
            return True
        node = node.parent
    return False


def parse_general_result(sub: Node, sub_rank: int = 0) -> dict[str, Any]:
    if is_general_video(sub):
        return parse_general_video(sub, sub_rank=sub_rank)

    title_div = subtree_first(sub, "div.rc") or subtree_first(sub, "div.yuRUbf")
    body_div = subtree_first(sub, "span.st") or subtree_first(sub, "div.VwiC3b")

    title_h3 = title_div.css_first("h3") if title_div is not None else None
    title_a = title_div.css_first("a") if title_div is not None else None
    cite_el = subtree_first(sub, "cite")

    parsed: dict[str, Any] = {
        "type": "general",
        "sub_rank": sub_rank,
        "title": get_text(title_h3, " "),
        "url": title_a.attrs.get("href") if title_a is not None else None,
        "text": get_text(body_div, " "),
        "cite": get_text(cite_el, " "),
    }

    return parse_subtype_details(sub, parsed)


def parse_subtype_details(sub: Node, parsed: dict[str, Any]) -> dict[str, Any]:
    details: dict[str, Any] = {}

    # If top menu with children, ignore URLs and get correct title URL.
    top_menu = sub.css_first("div.yWc32e")
    if top_menu is not None:
        children = list(top_menu.iter(include_text=False))
        if children:
            for child in children:
                child.decompose()
            h3 = sub.css_first("h3")
            if h3 is not None:
                a = h3.css_first("a")
                if a is not None:
                    parsed["url"] = a.attrs.get("href")

    sub_classes = class_tokens(sub)
    if "d4rhi" in sub_classes:
        # Host-group sub-results Google stacks/indents under a same-host main
        # result -- full organic results, tagged so downstream can identify them.
        parsed["sub_type"] = "indented"

    elif sub.css_first("div.d86Vh") is not None:
        # Image thumbnail strip (e.g. Pinterest board, Etsy market, shop pages):
        # a horizontal row of g-img previews that all link back to the result.
        # The thumbnails are JS-driven data: placeholders with no per-image url
        # or alt text, so only the layout is flagged -- there is nothing that
        # fits an existing details schema to capture.
        parsed["sub_type"] = "image_strip"

    elif (stars := sub.css_first("g-review-stars")) is not None:
        # Submenu - rating
        parsed["sub_type"] = "submenu_rating"
        sibling = next_sibling(stars)
        if sibling is not None:
            # The sibling is usually a bare text node (" Rating: 4.5 - 12 votes");
            # ``str(node)`` would be the selectolax repr, not its text.
            text = (get_text(sibling) or "").strip()
            if text:
                ratings = parse_ratings(text.split("-"))
                details.update(ratings)
                details["type"] = "review"

    elif (submenu_div := sub.css_first("div.P1usbc, div.IThcWe")) is not None:
        # Submenu - list format
        parsed["sub_type"] = "submenu"
        alinks = list(submenu_div.css("a"))
        details["type"] = "hyperlinks"
        details["items"] = parse_alink_list(alinks)

    elif (table := sub.css_first("table")) is not None:
        # Submenu - table format
        parsed["sub_type"] = "submenu"
        alinks = list(table.css("a"))
        details["type"] = "hyperlinks"
        details["items"] = parse_alink_list(alinks)

    elif (submenu := sub.css_first("div.osl, div.jYOxx")) is not None:
        # Mini submenu
        parsed["sub_type"] = "submenu_mini"
        alinks = list(submenu.css("a"))
        details["type"] = "hyperlinks"
        details["items"] = parse_alink_list(alinks)

    elif (scholar_div := sub.css_first('div[class*="fG8Fp"]')) is not None:
        # bs4 ``find("div", {"class": re.compile("fG8Fp")})`` is regex substring
        # match; CSS ``[class*="fG8Fp"]`` is the same substring semantics here.
        alinks = list(scholar_div.css("a"))
        if alinks and "Cited by" in (get_text(alinks[0]) or ""):
            # Scholar results
            parsed["sub_type"] = "submenu_scholarly"
            details["type"] = "hyperlinks"
            details["items"] = parse_alink_list(alinks)

        # Product results
        text = get_text(scholar_div, " ") or ""
        if not alinks and "$" in text:
            parsed["sub_type"] = "submenu_product"
            details.update(parse_product(text))
            details["type"] = "product"

    elif (rating_span := sub.css_first("span.Y0A0hc, span.z3HNkc")) is not None:
        # Modern rating widget (e.g. entertainment titles with star ratings)
        ratings = parse_rating_aria_label(str(rating_span.attrs.get("aria-label", "")))
        if ratings:
            details["type"] = "ratings"
            details.update(ratings)

    parsed["details"] = details if details else None
    return parsed


_ARIA_RATING_RE = re.compile(r"Rated\s+(\d+(?:\.\d+)?)\s+out of\s+(\d+)")
_ARIA_REVIEWS_RE = re.compile(r"\(([\d,]+)\)\s*user reviews?")
# A number with at least one digit (``4``, ``4.5``, ``.5``, ``5.``); the previous
# ``^\d*[.]?\d*$`` also matched ``""`` and ``"."``, which ``float`` rejects.
_RATING_NUMERIC_RE = re.compile(r"^(?:\d+\.?\d*|\.\d+)$")
_RATING_VOTES_RE = re.compile(r" vote[s]?| review[s]?")
_RATING_REVIEW_BY_RE = re.compile("Review by")
_PRODUCT_SPLIT_RE = re.compile("-|·")


def parse_rating_aria_label(aria_label: str) -> dict[str, Any]:
    """Parse 'Rated 2.5 out of 5, (5,114) user reviews' into structured fields."""
    rating_match = _ARIA_RATING_RE.search(aria_label or "")
    if not rating_match:
        return {}
    result: dict[str, Any] = {
        "rating": float(rating_match.group(1)),
        "scale": int(rating_match.group(2)),
    }
    reviews_match = _ARIA_REVIEWS_RE.search(aria_label)
    if reviews_match:
        result["n_reviews"] = int(reviews_match.group(1).replace(",", ""))
    return result


def parse_ratings(parts: list[str]) -> dict[str, Any]:
    text = [t.strip() for t in parts]
    rating = re.split("Rating: ", text[0])[-1]
    details: dict[str, Any] = (
        {"rating": float(rating)} if _RATING_NUMERIC_RE.match(rating) else {"rating": rating}
    )

    if len(text) > 1:
        if _RATING_VOTES_RE.search(text[1]):
            # Keep only the digits: the count may be prefixed by a bullet or
            # other unicode glyph and may carry thousands separators.
            digits = re.sub(r"\D", "", re.split(_RATING_VOTES_RE, text[1])[0])
            if digits:
                details["reviews"] = int(digits)
        elif _RATING_REVIEW_BY_RE.search(text[1]):
            details["reviews"] = 1

    return details


def parse_product(text: str) -> dict[str, Any]:
    parts = re.split(_PRODUCT_SPLIT_RE, text)
    if len(parts) == 1:
        return {"price": parts[0].strip()[1:]}
    return {"price": parts[0].strip()[1:], "stock": parts[1].strip()[1:]}


# General Video Results -----------------------------------------------------


def is_general_video(sub: Node) -> bool:
    return "PmEWq" in class_tokens(sub)


def parse_general_video(sub: Node, sub_rank: int = 0) -> dict[str, Any]:
    a = sub.css_first("a[href]")
    title_el = sub.css_first("h3.LC20lb")
    body_el = sub.css_first(".ITZIwc")
    cite_el = sub.css_first("cite")
    fields = parse_evlb_card(sub) or {}
    # Duration only exists on the visible tile's overlay (older layouts), never
    # in the hidden card -- keep its selector as a merged legacy path.
    duration = get_text(sub.css_first(".JIv15d"), strip=True)
    if duration:
        fields["duration"] = duration
    return {
        "type": "general",
        "sub_type": "video",
        "sub_rank": sub_rank,
        "title": get_text(title_el, strip=True),
        "url": a.attrs.get("href", "") if a is not None else None,
        "text": get_text(body_el, strip=True),
        "cite": get_text(cite_el, strip=False),
        "details": {"type": "video", **fields} if fields else None,
    }
