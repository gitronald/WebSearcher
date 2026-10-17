"""Regression tests for parser edge cases found in the whole-package review.

Each test builds the smallest HTML that exercised a crash or wrong field and
pins the corrected behavior.
"""

import pytest

from WebSearcher._slx import make_soup
from WebSearcher.models.data import ERR_NO_SUBCOMPONENTS
from WebSearcher.parsers.components import footer, general, shopping_ads, top_stories, videos
from WebSearcher.parsers.components._ai_overview_payloads import _decode_js_string, extract_payloads
from WebSearcher.parsers.components.general_questions import parse_general_questions
from WebSearcher.parsers.components.news_quotes import parse_news_quote, parse_news_quotes
from WebSearcher.parsers.components.scholarly_articles import parse_article
from WebSearcher.parsers.components.short_videos import parse_short_videos
from WebSearcher.parsers.components.twitter_cards import parse_twitter_header
from WebSearcher.parsers.components.twitter_result import parse_twitter_result
from WebSearcher.parsers.components.view_more_news import parse_sub, parse_view_more_news


def _node(html: str, css: str):
    node = make_soup(html).css_first(css)
    assert node is not None
    return node


# news_quotes -----------------------------------------------------------------


def test_news_quote_single_child_card_does_not_raise():
    card = _node("<g-inner-card><div>Just a quote</div></g-inner-card>", "g-inner-card")
    assert parse_news_quote(card) == {"type": "news_quotes", "sub_rank": 0, "text": "Just a quote"}


def test_news_quote_four_child_card_keeps_quote_text():
    html = "<g-inner-card><div>Q</div><div></div><div></div><div>extra</div></g-inner-card>"
    parsed = parse_news_quote(_node(html, "g-inner-card"))
    assert parsed["text"] == "Q"


def test_news_quote_single_child_result_does_not_raise():
    html = "<g-inner-card><div>Q</div><div><a href='/u'>T</a></div></g-inner-card>"
    parsed = parse_news_quote(_node(html, "g-inner-card"))
    assert parsed["text"] == "Q"
    assert "title" not in parsed


def test_news_quote_two_child_result_with_text_meta_keeps_text():
    html = "<g-inner-card><div>Q</div><div><a href='/u'>T</a>meta</div></g-inner-card>"
    parsed = parse_news_quote(_node(html, "g-inner-card"))
    assert parsed["title"] == "T"
    assert parsed["url"] == "/u"
    assert parsed["text"] == "Q"


def test_news_quotes_component_survives_odd_card():
    html = (
        "<div><g-inner-card><div>A</div><div><a href='/a'>T</a><div><span>c</span>"
        "<span>1d</span></div></div></g-inner-card><g-inner-card><div>odd</div></g-inner-card></div>"
    )
    rows = parse_news_quotes(_node(html, "div"))
    assert [r["sub_rank"] for r in rows] == [0, 1]
    assert rows[0]["cite"] == "c"
    assert rows[1]["text"] == "odd"


# href-less anchors --------------------------------------------------------------


def test_scholarly_article_anchor_without_href():
    parsed = parse_article(_node("<div><a>Paper</a><span>cite</span></div>", "div"))
    assert parsed["url"] is None
    assert parsed["title"] == "Paper"


def test_twitter_result_anchor_without_href():
    html = "<div><div class='DOqJne'><g-link><a>Acct</a></g-link></div></div>"
    [parsed] = parse_twitter_result(_node(html, "div"))
    assert parsed["title"] == "Acct"
    assert parsed["url"] is None


def test_view_more_news_anchor_without_href():
    parsed = parse_sub(_node("<div><a>x</a><div class='jBgGLd'>T</div></div>", "div"))
    assert parsed["url"] is None
    assert parsed["title"] == "T"


def test_general_top_menu_anchor_without_href():
    html = (
        "<div class='g'><div class='yWc32e'><span>m</span></div>"
        "<div class='yuRUbf'><h3><a>T</a></h3></div></div>"
    )
    [parsed] = general.parse_general_results(_node(html, "div.g"))
    assert parsed["title"] == "T"
    assert parsed["url"] is None


# twitter_cards legacy header ----------------------------------------------------


def test_twitter_header_legacy_url_comes_from_anchor():
    html = "<div><h3 class='r'><a href='https://twitter.com/acct'>Acct</a></h3></div>"
    parsed = parse_twitter_header(_node(html, "div"))
    assert parsed["url"] == "https://twitter.com/acct"
    assert parsed["title"] == "Acct"


# comment nodes and overlapping selectors ----------------------------------------


_CARD = "<g-inner-card><div class='n0jPhd'>{t}</div><a href='/{t}'>l</a></g-inner-card>"


def test_top_stories_comment_node_is_not_a_row():
    html = f"<div><div class='qmv19b'>{_CARD.format(t='a')}<!-- sep -->{_CARD.format(t='b')}</div></div>"
    rows = top_stories.parse_top_stories(_node(html, "div"))
    assert [(r["sub_rank"], r["title"]) for r in rows] == [(0, "a"), (1, "b")]


def test_top_stories_overlapping_selectors_do_not_duplicate_cards():
    html = f"<div><div class='qmv19b'>{_CARD.format(t='a')}{_CARD.format(t='b')}</div></div>"
    rows = top_stories.parse_top_stories(_node(html, "div"))
    assert [r["title"] for r in rows] == ["a", "b"]


def test_view_more_news_comment_node_is_not_a_row():
    html = "<div><div class='qmv19b'><div><a href='/a'>a</a></div><!-- x --><div><a href='/b'>b</a></div></div></div>"
    rows = parse_view_more_news(_node(html, "div"))
    assert [r["url"] for r in rows] == ["/a", "/b"]


# videos text separator ----------------------------------------------------------


def test_video_text_keeps_fragment_separator():
    html = "<div class='sHEJob'><a href='/v'>l</a><div class='MjS0Lc'><span>Title</span><span>Channel</span></div></div>"
    parsed = videos.parse_video(_node(html, "div.sHEJob"), "vertical")
    assert parsed["text"] == "Title Channel"
    assert parsed["url"] == "/v"


# general submenu_rating ---------------------------------------------------------


def test_general_submenu_rating_reads_sibling_text():
    html = (
        "<div class='g'><div class='yuRUbf'><h3><a href='/u'>T</a></h3></div>"
        "<div><g-review-stars></g-review-stars> Rating: 4.5 - 12 votes</div></div>"
    )
    [parsed] = general.parse_general_results(_node(html, "div.g"))
    assert parsed["sub_type"] == "submenu_rating"
    assert parsed["details"] == {"rating": 4.5, "reviews": 12, "type": "review"}


def test_parse_ratings_edge_cases():
    assert general.parse_ratings(["Rating: 4.5", "• 1,234 votes"]) == {
        "rating": 4.5,
        "reviews": 1234,
    }
    assert general.parse_ratings(["4.5", "12 votes"]) == {"rating": 4.5, "reviews": 12}
    assert general.parse_ratings(["", " 12 votes"]) == {"rating": "", "reviews": 12}
    assert general.parse_ratings(["."]) == {"rating": "."}
    assert general.parse_ratings(["4", "Review by Jane"]) == {"rating": 4.0, "reviews": 1}


# general_questions ----------------------------------------------------------------


def test_general_questions_keeps_general_details_when_paa_is_empty():
    html = (
        "<div><div class='g'><div class='yuRUbf'><h3><a href='/u'>T</a></h3></div>"
        "<div class='osl'><a href='/s1'>s1</a></div></div></div>"
    )
    [parsed] = parse_general_questions(_node(html, "div"))
    assert parsed["type"] == "general_questions"
    assert parsed["sub_type"] == "submenu_mini"
    assert parsed["details"] == {"type": "hyperlinks", "items": [{"url": "/s1", "text": "s1"}]}


# hollow payloads ------------------------------------------------------------------


def test_short_videos_empty_component_reports_no_subcomponents():
    [row] = parse_short_videos(_node("<div><p>nothing</p></div>", "div"))
    assert row["details"]["error"] == ERR_NO_SUBCOMPONENTS


def test_sponsored_hotel_without_data_has_no_details():
    card = _node("<div><div class='KZYtMc'>Hotel</div><a href='/h'>l</a></div>", "div")
    parsed = shopping_ads._parse_sponsored_hotel(card)
    assert parsed["title"] == "Hotel"
    assert parsed["details"] is None


def test_img_card_without_alt_images_has_no_details():
    card = _node(
        "<div class='g'><div role='heading' aria-level='3'>T</div><img src='/i.png'></div>", "div.g"
    )
    parsed = footer.parse_img_card(card)
    assert parsed["title"] == "T"
    assert "details" not in parsed


# AI overview payload decoding --------------------------------------------------------


def test_ldpb_push_decodes_non_ascii_and_surrogate_pairs():
    uuid = "12345678-1234-1234-1234-123456789abd"
    raw = (
        r'(j.lDPB=j.lDPB||[]).push([["abc_68","[[\"'
        + uuid
        + r'\",[\"Café 😀\",\"Snippet \x3d ok\",\"https://fav\",\"https://dom\",[\"Pub\"],\"https://url\",null,null,\"5\",null,null,null]]]"]])'
    )
    out = extract_payloads(raw)
    assert uuid in out
    [type_a] = out[uuid]["type_a"]
    assert type_a["title"] == "Café 😀"
    assert type_a["snippet"] == "Snippet = ok"


@pytest.mark.parametrize(
    ("literal", "expected"),
    [
        (r"a\x41b", "aAb"),
        (r"a\\x41b", r"a\x41b"),
        (r"a\'b", "a'b"),
        (r"a\\'b", "a\\'b"),
        (r"a\\\'b", "a\\'b"),
        (r"\"q\" é", '"q" é'),
    ],
)
def test_decode_js_string_respects_escaped_backslashes(literal, expected):
    assert _decode_js_string(literal) == expected
