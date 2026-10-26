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
        "text",
        "carousel",
    }
    assert parse_ads(comp('<div class="uEierd"></div>')) == []


# 2026-10 text ad: no div.uEierd wrapper; the heading itself carries Va3FIb.
TEXT_AD = (
    '<div data-text-ad="1"><div class="v5yQqb">'
    '<a class="sVXRqc" data-pcu="https://shop.test/" href="/goto?url=tok">'
    '<div class="Va3FIb" role="heading" aria-level="3"><span>Shop Shoes</span></div>'
    '<span role="text">https://shop.test</span></a></div>'
    '<div class="p4wth">Free shipping on every order.</div>'
    '<div class="qmaLCb"><a href="/goto?url=a">Sale</a><a href="/aclk?b">New In</a></div>'
    "</div>"
)


def test_text_ad_dispatches_to_text_parser():
    rows = parse_ads(comp(TEXT_AD))
    assert rows == [
        {
            "type": "ad",
            "sub_type": "submenu",
            "sub_rank": 0,
            "title": "Shop Shoes",
            "url": "/goto?url=tok",
            "cite": "https://shop.test",
            "text": "Free shipping on every order.",
            "details": {
                "type": "menu",
                "items": [
                    {"url": "/goto?url=a", "title": "Sale"},
                    {"url": "/aclk?b", "title": "New In"},
                ],
            },
        }
    ]


def test_text_ad_yields_to_standard_wrapper():
    # Older text ads carry data-text-ad inside div.uEierd; parse them once.
    rows = parse_ads(
        comp('<div class="uEierd"><div data-text-ad="1"><div role="heading">A</div></div></div>')
    )
    assert [(r["sub_type"], r["title"]) for r in rows] == [("standard", "A")]


def test_text_ad_beside_wrapped_ad_is_kept():
    # A block mixing an older wrapped ad and a bare 2026-10 unit parses both,
    # each once.
    rows = parse_ads(
        comp(
            '<div class="uEierd"><div data-text-ad="1"><div role="heading">Old</div></div></div>'
            + TEXT_AD
        )
    )
    assert [(r["sub_type"], r["title"]) for r in rows] == [
        ("standard", "Old"),
        ("submenu", "Shop Shoes"),
    ]
