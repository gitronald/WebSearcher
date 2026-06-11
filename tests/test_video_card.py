"""Video details from hidden ``evlb_*`` "About this result" cards (plan 019).

Modern SERPs pre-render one hidden card per video tile carrying the clean
title, source, channel, publish date, and thumbnail URL. These tests pin the
card extraction helper on synthetic markup and the end-to-end enrichment on
the fixture corpus (the ``northern lights`` SERP's videos carousel).
"""

import bz2
from pathlib import Path

import orjson
import pytest

import WebSearcher as ws
from WebSearcher import utils
from WebSearcher.component_parsers._video_card import parse_evlb_card

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
