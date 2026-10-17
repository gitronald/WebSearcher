"""Regression tests for extractor and Component edge cases found in the
whole-package review (empty ad shells, padded labels, duplicated footer notices,
unknown rhs layouts, malformed parser rows, ad sub_rank numbering)."""

import pytest

import WebSearcher as ws
from WebSearcher._slx import make_soup
from WebSearcher.extractors.extractor_main import ExtractorMain
from WebSearcher.models.data import ERR_EXCEPTION
from WebSearcher.parsers import component as component_mod
from WebSearcher.parsers.component import Component
from WebSearcher.parsers.component_list import ComponentList
from WebSearcher.parsers.components.ads import parse_ad_carousel, parse_ads

ORGANIC = (
    '<div id="rso"><div class="g"><div class="yuRUbf"><h3><a href="https://e.com">T</a></h3>'
    "</div><div class='VwiC3b'>snippet</div></div></div>"
)


def _types(parsed: dict) -> list[tuple[str, str]]:
    return [(r["section"], r["type"]) for r in parsed["results"]]


def _node(html: str, css: str):
    node = make_soup(html).css_first(css)
    assert node is not None
    return node


# extractor_main ------------------------------------------------------------------


def test_whitespace_only_ad_shell_is_not_a_component():
    parsed = ws.parse_serp(f'<div id="tads">\n  <div></div>\n</div>{ORGANIC}')
    assert _types(parsed) == [("main", "general")]


def test_ad_shell_with_text_is_still_extracted():
    parsed = ws.parse_serp(f'<div id="tads"><div class="uEierd">Sponsored</div></div>{ORGANIC}')
    assert ("main", "ad") in _types(parsed)


def test_is_valid_strips_padded_bad_labels():
    node = _node("<div><h2> Main results </h2></div>", "div")
    assert ExtractorMain.is_valid(node) is False
    real = _node("<div><h2> Main results </h2><p>content</p></div>", "div")
    assert ExtractorMain.is_valid(real) is True


def test_no_rso_twitter_section_uses_inner_div_parent():
    html = (
        '<div class="UDZeY OTFaAf"><h2>Twitter Results</h2>'
        '<div id="inner"><div>tweet</div></div></div>'
    )
    soup = make_soup(html)
    extractor = ExtractorMain(soup, ComponentList())
    [out] = extractor.extract_from_no_rso()
    # bs4 ``div.find("div").parent`` is the section itself, not its parent.
    assert out.attrs.get("class") == "UDZeY OTFaAf"


# extractor_footer ------------------------------------------------------------------


def test_omitted_notice_nested_in_bres_is_emitted_once():
    html = (
        f'{ORGANIC}<div id="botstuff"><div id="bres">'
        '<div class="ClPXac">Notices about Filtered Results</div></div></div>'
    )
    parsed = ws.parse_serp(html)
    footer = [r for r in parsed["results"] if r["section"] == "footer"]
    assert len(footer) == 1


def test_omitted_notice_outside_bres_is_still_emitted():
    html = (
        f'{ORGANIC}<div id="botstuff"><div id="bres"><p>related</p></div></div>'
        '<div class="ClPXac">Notices about Filtered Results</div>'
    )
    parsed = ws.parse_serp(html)
    footer = [r for r in parsed["results"] if r["section"] == "footer"]
    assert len(footer) == 2


def test_omitted_notice_in_hidden_bres_is_still_emitted():
    # The hidden-footer filter drops #bres here, so the nested notice must
    # not be deduplicated against it.
    html = (
        f'{ORGANIC}<div id="botstuff"><div id="bres">'
        '<div class="ClPXac">Notices about Filtered Results</div>'
        '<span class="oUAcPd">hidden</span></div></div>'
    )
    parsed = ws.parse_serp(html)
    footer = [r for r in parsed["results"] if r["section"] == "footer"]
    assert len(footer) == 1


# extractor_rhs ---------------------------------------------------------------------


def test_unknown_rhs_layout_is_kept_as_unknown_component():
    parsed = ws.parse_serp(f'{ORGANIC}<div id="rhs"><div class="NewClass">hello world</div></div>')
    assert ("rhs", "unknown") in _types(parsed)
    [rhs] = [r for r in parsed["results"] if r["section"] == "rhs"]
    assert rhs["text"] == "hello world"


def test_empty_rhs_is_dropped():
    parsed = ws.parse_serp(f'{ORGANIC}<div id="rhs"><div class="NewClass"> </div></div>')
    assert all(r["section"] != "rhs" for r in parsed["results"])


# Component -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_row", [{"type": "x", "sub_rank": None}, "notadict", {"sub_rank": "a"}]
)
def test_malformed_parser_row_becomes_error_row(monkeypatch, bad_row):
    elem = _node('<div class="g">x</div>', "div.g")
    cmpt = Component(elem, section="main", type="general")
    monkeypatch.setitem(component_mod.main_parser_dict, "general", lambda node: [bad_row])
    cmpt.parse_component()  # must not raise
    [row] = cmpt.result_list
    assert row["type"] == "general"
    assert row["details"]["error"].startswith(ERR_EXCEPTION)


# ads -------------------------------------------------------------------------------


_LEGACY = (
    '<ul><li class="ads-ad"><div class="ad_cclk"><h3>A1</h3></div></li>'
    '<li class="ads-ad"><div class="ad_cclk"><h3>A2</h3></div></li></ul>'
)
_CAROUSEL = (
    "<g-scrolling-carousel>"
    '<g-inner-card><div class="gCv54b">C1</div></g-inner-card>'
    '<g-inner-card data-viewurl="x"><div class="gCv54b">hidden</div></g-inner-card>'
    '<g-inner-card><div class="gCv54b">C2</div></g-inner-card>'
    "</g-scrolling-carousel>"
)


def test_parse_ads_renumbers_sub_rank_across_layouts():
    node = _node(f"<div>{_LEGACY}{_CAROUSEL}</div>", "div")
    rows = parse_ads(node)
    assert [(r["sub_type"], r["sub_rank"]) for r in rows] == [
        ("legacy", 0),
        ("legacy", 1),
        ("carousel", 2),
        ("carousel", 3),
    ]


def test_parse_ad_carousel_skips_hidden_cards_without_gaps():
    node = _node(f"<div>{_CAROUSEL}</div>", "div")
    rows = parse_ad_carousel(node)
    assert [(r["title"], r["sub_rank"]) for r in rows] == [("C1", 0), ("C2", 1)]


def test_rhs_with_knowledge_attrids_routes_to_knowledge_rhs():
    html = (
        f'{ORGANIC}<div id="rhs"><div class="jOAHU"><h2 data-attrid="title">Ada Lovelace</h2>'
        '<div data-attrid="kc:/people/person:born"><span>Born</span><span>1815</span></div>'
        "</div></div>"
    )
    parsed = ws.parse_serp(html)
    rhs = [r for r in parsed["results"] if r["section"] == "rhs"]
    assert rhs and all(r["type"] != "unknown" for r in rhs)
