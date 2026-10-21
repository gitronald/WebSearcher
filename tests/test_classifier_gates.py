"""Classifier-chain regressions from the whole-package review: preconditions must
be necessary conditions for the classifier they gate, every type the chain can
emit must be registered, and the chain table is built once."""

from WebSearcher._slx import make_soup
from WebSearcher.classifiers import ClassifyMain
from WebSearcher.classifiers.main import _COMPONENT_CLASSIFIERS
from WebSearcher.parsers.component_types import TYPES_BY_NAME


def _cmpt(inner: str):
    node = make_soup(f'<div class="wrap">{inner}</div>').css_first("div.wrap")
    assert node is not None
    return node


def test_products_classifies_apg_product_result_without_gate_tokens():
    cmpt = _cmpt('<div data-attrid="apg-product-result"><a href="/p">Shoe</a></div>')
    assert ClassifyMain.products(cmpt) == "products"
    assert ClassifyMain.classify(cmpt) == "products"


def test_products_classifies_explore_brands_heading():
    cmpt = _cmpt('<div role="heading">Explore brands</div><div><a href="/b">Brand</a></div>')
    assert ClassifyMain.classify(cmpt) == "products"


def test_ai_overview_banner_classifies_controller_without_wrapper_class():
    cmpt = _cmpt('<div jscontroller="EYwa3d"><span>Thinking</span></div>')
    assert ClassifyMain.classify(cmpt) == "ai_overview"


def test_knowledge_box_types_are_registered():
    for html, expected in [
        ('<div jscontroller="Z2bSc">f</div>', "flights"),
        ('<div class="zd2Jbb">l</div>', "locations"),
        ('<g-card class="URhAHe">e</g-card>', "events"),
        ('<g-card class="cvoI5e">j</g-card>', "jobs"),
        ("<span>COVID-19 alert</span><p>x</p>", "covid_alert"),
    ]:
        assert ClassifyMain.knowledge_box(_cmpt(html)) == expected
        assert expected in TYPES_BY_NAME
    maps = make_soup('<div data-hveid="CAMQAA">m</div>').css_first("div")
    assert maps is not None
    assert ClassifyMain.knowledge_box(maps) == "maps"
    assert "maps" in TYPES_BY_NAME


def test_twitter_heading_block_and_large_component():
    assert ClassifyMain.twitter(_cmpt("<h2>Twitter Results</h2>")) == "twitter_result"
    carousel = _cmpt("<div class='eejeod'>t</div><g-scrolling-carousel></g-scrolling-carousel>")
    assert ClassifyMain.twitter(carousel) == "twitter_cards"
    big = _cmpt("<p>" + "Twitter Results and a lot more text " * 50 + "</p>")
    assert ClassifyMain.twitter(big) == "unknown"


def test_classifier_table_ends_with_ungated_banner():
    assert _COMPONENT_CLASSIFIERS[-1][0] is ClassifyMain.ai_overview_banner
    assert _COMPONENT_CLASSIFIERS[-1][1] is None
