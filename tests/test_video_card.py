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
from selectolax.lexbor import LexborNode as Node

import WebSearcher as ws
from WebSearcher import utils
from WebSearcher.parsers.components._video_card import evlb_fields_by_tile, parse_evlb_card
from WebSearcher.parsers.components.general import parse_general_video
from WebSearcher.parsers.components.videos import parse_videos

SERPS_PATH = Path(__file__).parent / "fixtures" / "serps.json.bz2"


def _node(html: str) -> Node:
    node = utils.make_soup(f"<div>{html}</div>").css_first("div")
    assert node is not None
    return node


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


def test_parse_evlb_card_thumbnail_only_stub_is_skipped():
    # A stub shipping only a lazy-load placeholder img must not count as
    # populated -- it would otherwise shadow the real card behind it.
    stub = '<div id="evlb_stub"><img class="aLL3sb" src="data:image/gif;base64,R0"></div>'
    fields = parse_evlb_card(_node(f"{stub}{CARD_HTML}"))
    assert fields is not None
    assert fields["channel"] == "Robservatory"
    assert parse_evlb_card(_node(stub)) is None


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
    assert root is not None
    assert evlb_fields_by_tile(root, root.css("a.rIRoqf")) == {}


def test_fields_by_tile_skips_ambiguous_wrapper():
    # One wrapper around two tiles cannot say whose card it holds.
    root = _node(
        '<div class="WVV5ke"><a class="rIRoqf" href="http://v1">a</a>'
        f'<a class="rIRoqf" href="http://v2">b</a>{CARD_HTML}</div>'
    )
    assert evlb_fields_by_tile(root, root.css("a.rIRoqf")) == {}


def test_fields_by_tile_skips_wrapper_with_multiple_cards():
    # A wide wrapper holding one qualifying tile but several videos' cards
    # (the other anchors filtered out by the caller) cannot say which card
    # belongs to the tile.
    card2 = CARD_HTML.replace("evlb_abc", "evlb_def").replace("Robservatory", "OtherChannel")
    root = _node(
        f'<div class="WVV5ke"><a class="rIRoqf" href="http://v1">tile</a>{CARD_HTML}{card2}</div>'
    )
    assert evlb_fields_by_tile(root, root.css("a.rIRoqf")) == {}


# --- fixture corpus: end-to-end enrichment ----------------------------------


CORPUS_QUERIES = {"@nasa", "northern lights", "art deco architecture"}


@pytest.fixture(scope="module")
def corpus_results() -> list[tuple[str, list[dict]]]:
    """Parsed results for the card-bearing fixture SERPs, one parse per record."""
    with bz2.open(SERPS_PATH, "rt") as f:
        records = [r for line in f if (r := orjson.loads(line))["qry"] in CORPUS_QUERIES]
    return [(rec["qry"], ws.parse_serp(rec["html"])["results"]) for rec in records]


def test_videos_carousel_details_enriched(corpus_results):
    results = next(res for qry, res in corpus_results if qry == "northern lights")
    videos = [r for r in results if r["type"] == "videos"]
    assert len(videos) == 3
    for r in videos:
        details = r["details"]
        assert details["type"] == "video"
        assert details["source"] == "YouTube"
        assert details["publish_date"]
        assert details["thumbnail_url"]
    channels = {r["details"]["channel"] for r in videos}
    assert channels == {"GeologyHub", "Late Night Astronomy", "Robservatory"}


def test_enriched_thumbnail_matches_row_video_id(corpus_results):
    """Attribution invariant: for YouTube rows with a ytimg thumbnail, the
    video id embedded in the card's thumbnail must match the row URL's id --
    a mismatch would mean a card was pulled from a different result."""
    checked = 0
    for _qry, results in corpus_results:
        for r in results:
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


# --- key moments, from deferred fragments ---------------------------------------


def _fragment(target_id: str, body: str) -> str:
    return f"<script>[{{id:'{target_id}'}},function(){{jsl.dh(this.id,\"{body}\");}}]</script>"


_EXPANDER_MOMENTS = (
    r"\x3ca data-time=\"0\" href=\"/goto?url=M0\""
    r" aria-label=\"Intro. Part one. 1 of 2, 0 seconds. \">\x3cimg>\x3c/a>"
    r"\x3ca data-time=\"188\" href=\"/goto?url=M1\""
    r" aria-label=\"Basics. 2 of 2, 3 minutes, 8 seconds. \">\x3cimg>\x3c/a>"
)
_CARD = (
    r"\x3cspan class=\"PNsAZd\">A channel\x3c/span>\x3cspan class=\"DKsccc\">Jun 5, 2026\x3c/span>"
    r"\x3cdiv role=\"heading\">In this video\x3c/div>"
    r"\x3ca data-time=\"0\" href=\"/goto?url=M0\">\x3cspan>00:00\x3c/span>\x3cspan>Intro\x3c/span>\x3c/a>"
    r"\x3ca data-time=\"188\" href=\"/goto?url=M1\">\x3cspan>03:08\x3c/span>\x3cspan>Basics\x3c/span>\x3c/a>"
)


def _videos_page(tile_body: str, fragments: str) -> Node:
    html = (
        '<div id="scope"><div class="sHEJob">'
        '<a href="/goto?url=VIDEO"></a><div role="heading">A video</div>'
        f"{tile_body}</div></div>{fragments}"
    )
    node = utils.make_soup(html).css_first("#scope")
    assert node is not None
    return node


def test_video_row_reads_card_and_key_moments_from_fragments():
    node = _videos_page('<div style="display:none" id="evlb_1"></div>', _fragment("evlb_1", _CARD))
    [row] = parse_videos(node)
    assert row["title"] == "A video"
    assert row["url"] == "/goto?url=VIDEO"
    assert row["details"] == {
        "type": "video",
        "channel": "A channel",
        "publish_date": "Jun 5, 2026",
        "key_moments": [
            {"seconds": 0, "title": "Intro", "url": "/goto?url=M0"},
            {"seconds": 188, "title": "Basics", "url": "/goto?url=M1"},
        ],
    }


def test_key_moments_from_the_expander_and_the_card_count_once():
    node = _videos_page(
        '<div id="tsuid_1"></div><div style="display:none" id="evlb_1"></div>',
        _fragment("tsuid_1", _EXPANDER_MOMENTS) + _fragment("evlb_1", _CARD),
    )
    moments = parse_videos(node)[0]["details"]["key_moments"]
    assert [(m["seconds"], m["url"]) for m in moments] == [
        (0, "/goto?url=M0"),
        (188, "/goto?url=M1"),
    ]


def test_key_moments_from_the_expander_alone_have_no_title():
    # Its aria-label is a sentence in the page's language, so it is not parsed.
    node = _videos_page('<div id="tsuid_1"></div>', _fragment("tsuid_1", _EXPANDER_MOMENTS))
    assert [
        (m["seconds"], m["title"]) for m in parse_videos(node)[0]["details"]["key_moments"]
    ] == [
        (0, None),
        (188, None),
    ]


def test_a_video_with_no_fragment_has_no_details():
    assert parse_videos(_videos_page("<div>text</div>", ""))[0].get("details") is None


def test_a_browser_capture_keeps_its_filled_card():
    node = _videos_page(
        '<div id="evlb_1"><span class="PNsAZd">Kept</span></div>',
        _fragment("evlb_1", r"\x3cspan class=\"PNsAZd\">Overwritten\x3c/span>"),
    )
    assert parse_videos(node)[0]["details"]["channel"] == "Kept"


def test_general_video_reads_moments_without_changing_its_core_fields():
    node = utils.make_soup(
        '<div id="tile" class="PmEWq"><a href="/goto?url=VIDEO"></a><h3 class="LC20lb">A video</h3>'
        '<span class="JIv15d">10:32</span><div id="evlb_1"></div></div>'
        + _fragment("evlb_1", _CARD)
    ).css_first("#tile")
    assert node is not None
    row = parse_general_video(node)
    assert (row["title"], row["url"]) == ("A video", "/goto?url=VIDEO")
    assert row["details"]["duration"] == "10:32"
    assert [m["seconds"] for m in row["details"]["key_moments"]] == [0, 188]


# --- the heading's title and source line -----------------------------------------


def _heading_tile(heading: str, extra: str = "") -> Node:
    node = utils.make_soup(
        f'<div id="scope"><div class="sHEJob"><a href="/v"></a>'
        f'<div role="heading">{heading}</div>{extra}</div></div>'
    ).css_first("#scope")
    assert node is not None
    return node


_TWO_PARTS = (
    "<div><span>A video</span></div>"
    "<div><span>YouTube</span><span><span> ·</span> A channel</span><div>May 20, 2025</div></div>"
)


def test_a_two_part_heading_gives_a_title_and_a_cite():
    [row] = parse_videos(_heading_tile(_TWO_PARTS))
    assert row["title"] == "A video"
    assert row["cite"] == "YouTube · A channel May 20, 2025"


def test_the_source_line_replaces_a_cite_it_contains():
    [row] = parse_videos(_heading_tile(_TWO_PARTS, "<cite>YouTube</cite>"))
    assert row["cite"] == "YouTube · A channel May 20, 2025"


def test_a_different_cite_of_the_tiles_own_is_kept():
    [row] = parse_videos(_heading_tile(_TWO_PARTS, "<cite>www.example.com</cite>"))
    assert row["title"] == "A video"
    assert row["cite"] == "www.example.com"


@pytest.mark.parametrize(
    "heading",
    [
        "A video",
        "<span>A video</span>",
        "<div>A video</div><div>one</div><div>two</div>",
        "<div></div><div>A video</div>",
    ],
)
def test_any_other_heading_is_read_whole_with_no_cite(heading):
    [row] = parse_videos(_heading_tile(heading))
    assert "A video" in row["title"]
    assert row.get("cite") is None
