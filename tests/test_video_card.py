"""Video details from hidden ``evlb_*`` "About this result" cards (plan 019).

Modern SERPs pre-render one hidden card per video tile carrying the clean
title, source, channel, publish date, and thumbnail URL. These tests pin the
card extraction helper on synthetic markup and the end-to-end enrichment on
the fixture corpus (the ``northern lights`` SERP's videos carousel).
"""

import bz2
import re
from pathlib import Path

import orjson
import pytest

import WebSearcher as ws
from WebSearcher import utils
from WebSearcher.component_parsers._video_card import evlb_fields_by_tile, parse_evlb_card

SERPS_PATH = Path(__file__).parent / "fixtures" / "serps.json.bz2"


def _node(html: str):
    return utils.make_soup(f"<div>{html}</div>").css_first("div")


CARD_HTML = (
    '<div id="evlb_abc" style="display:none"><div class="F9x6yb">'
    '<h1 class="WQWxe">What are the Northern Lights?</h1>'
    '<img class="aLL3sb" src="https://i.ytimg.com/vi/x/hqdefault.jpg">'
    '<span class="KrMNbf">YouTube</span>'
    '<span class="PNsAZd">Robservatory</span>'
    '<span class="DKsccc">Nov 11, 2025</span>'
    "</div></div>"
)


def test_parse_evlb_card_populated():
    fields = parse_evlb_card(_node(f"<div>tile</div>{CARD_HTML}"))
    assert fields == {
        "title": "What are the Northern Lights?",
        "source": "YouTube",
        "channel": "Robservatory",
        "publish_date": "Nov 11, 2025",
        "thumbnail_url": "https://i.ytimg.com/vi/x/hqdefault.jpg",
    }


def test_parse_evlb_card_empty_stub_is_none():
    # Older SERPs ship empty template stubs under the same ids.
    sub = _node('<div>tile</div><div id="evlb_abc" style="display:none"></div>')
    assert parse_evlb_card(sub) is None


def test_parse_evlb_card_absent_is_none():
    assert parse_evlb_card(_node("<div>tile</div>")) is None


def test_parse_evlb_card_skips_stub_before_populated_card():
    sub = _node(f'<div id="evlb_stub"></div>{CARD_HTML}')
    fields = parse_evlb_card(sub)
    assert fields is not None
    assert fields["channel"] == "Robservatory"


# --- evlb_fields_by_tile: wrapper association stays inside the component ----


def test_fields_by_tile_pairs_wrapper_with_single_tile():
    root = _node(
        f'<div class="WVV5ke"><a class="rIRoqf" href="http://v1">tile</a>{CARD_HTML}</div>'
    )
    tiles = root.css("a.rIRoqf")
    fields = evlb_fields_by_tile(root, tiles)
    assert fields == {tiles[0].mem_id: parse_evlb_card(root)}


def test_fields_by_tile_ignores_card_outside_root():
    # The card sits in a NEIGHBORING component's wrapper -- a lookup scoped to
    # this component must not borrow it.
    doc = utils.make_soup(
        '<div><div id="cmpt"><a class="rIRoqf" href="http://v1">tile</a></div>'
        f'<div class="WVV5ke">{CARD_HTML}</div></div>'
    )
    root = doc.css_first("div#cmpt")
    assert evlb_fields_by_tile(root, root.css("a.rIRoqf")) == {}


def test_fields_by_tile_skips_ambiguous_wrapper():
    # One wrapper around two tiles cannot say whose card it holds.
    root = _node(
        '<div class="WVV5ke"><a class="rIRoqf" href="http://v1">a</a>'
        f'<a class="rIRoqf" href="http://v2">b</a>{CARD_HTML}</div>'
    )
    assert evlb_fields_by_tile(root, root.css("a.rIRoqf")) == {}


# --- fixture corpus: end-to-end enrichment ----------------------------------


@pytest.fixture(scope="module")
def northern_lights_results() -> list[dict]:
    with bz2.open(SERPS_PATH, "rt") as f:
        rec = next(r for line in f if (r := orjson.loads(line))["qry"] == "northern lights")
    return ws.parse_serp(rec["html"])["results"]


def test_videos_carousel_details_enriched(northern_lights_results):
    videos = [r for r in northern_lights_results if r["type"] == "videos"]
    assert len(videos) == 3
    for r in videos:
        details = r["details"]
        assert details["type"] == "video"
        assert details["source"] == "YouTube"
        assert details["publish_date"]
        assert details["thumbnail_url"]
    channels = {r["details"]["channel"] for r in videos}
    assert channels == {"GeologyHub", "Late Night Astronomy", "Robservatory"}


def test_enriched_thumbnail_matches_row_video_id():
    """Attribution invariant: for YouTube rows with a ytimg thumbnail, the
    video id embedded in the card's thumbnail must match the row URL's id --
    a mismatch would mean a card was pulled from a different result."""
    queries = {"@nasa", "northern lights", "art deco architecture"}
    checked = 0
    with bz2.open(SERPS_PATH, "rt") as f:
        records = [r for line in f if (r := orjson.loads(line))["qry"] in queries]
    for rec in records:
        for r in ws.parse_serp(rec["html"])["results"]:
            d = r.get("details")
            url = r.get("url") or ""
            if not (isinstance(d, dict) and d.get("type") == "video"):
                continue
            m_url = re.search(r"[?&]v=([\w-]{11})|/shorts/([\w-]{11})", url)
            m_thumb = re.search(r"/vi/([\w-]{11})/", d.get("thumbnail_url") or "")
            if m_url and m_thumb:
                row_id = m_url.group(1) or m_url.group(2)
                assert m_thumb.group(1) == row_id, f"{url} got {d['thumbnail_url']}"
                checked += 1
    # Most thumbnails are data: lazy-load placeholders with no embedded id;
    # 9 rows on these SERPs carry a real /vi/<id>/ URL to cross-check.
    assert checked >= 5
