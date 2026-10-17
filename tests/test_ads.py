"""Tests for ad sub-type dispatch in ``parse_ads``."""

from selectolax.lexbor import LexborNode as Node

from WebSearcher import utils
from WebSearcher.parsers.components.ads import AD_SUBTYPE_SELECTORS, parse_ads


def comp(inner: str) -> Node:
    """Wrap inner HTML in a component ``Node`` (selectors match descendants, not self)."""
    node = utils.make_soup(f'<div class="wrap">{inner}</div>').css_first("div.wrap")
    assert node is not None
    return node


def test_standard_ad_dispatches_to_standard_parser():
    rows = parse_ads(comp('<div class="uEierd"><div role="heading">Sponsored</div></div>'))
    assert [(r["type"], r["sub_type"], r["title"]) for r in rows] == [
        ("ad", "standard", "Sponsored")
    ]


def test_legacy_ad_dispatches_to_legacy_parser():
    rows = parse_ads(comp('<ul><li class="ads-ad"><div class="ad_cclk"><h3>A</h3></div></li></ul>'))
    assert [(r["sub_type"], r["title"]) for r in rows] == [("legacy", "A")]


def test_no_ad_container_yields_no_rows():
    assert parse_ads(comp('<div class="g">An organic result</div>')) == []


def test_every_selector_has_a_parser():
    # parse_ads indexes its parser table by the selector label, so the two must
    # stay in step; an empty standard container matches the selector but yields
    # no rows because the sub-parser filters text-empty units.
    assert set(AD_SUBTYPE_SELECTORS) == {
        "legacy",
        "local_service",
        "secondary",
        "shopping",
        "standard",
        "carousel",
    }
    assert parse_ads(comp('<div class="uEierd"></div>')) == []
