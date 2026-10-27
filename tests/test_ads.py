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
        "listing",
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


def test_text_ad_with_place_card_links_through_data_pcu():
    # A location-extension text ad links through a.Zlr9V (not a.sVXRqc) and keeps
    # its description in div.aDWSGc.
    rows = parse_ads(
        comp(
            '<div data-text-ad="1"><div class="vt6azd"><div class="Tw0YHf">'
            '<a class="Zlr9V" data-pcu="https://paint.test/" href="/goto?url=p">'
            '<span role="text">https://paint.test</span></a>'
            '<div role="heading" aria-level="3">'
            '<a data-pcu="https://paint.test/" href="/goto?url=p"><span>Paint Co</span></a></div>'
            '</div><div class="aDWSGc"><span>Free estimates.</span></div>'
            '<div class="bn0HGf"><a href="https://www.google.com/aclk?w">Website</a></div>'
            "</div></div>"
        )
    )
    # The place card rides on a text ad with a landing URL, so it stays "standard".
    assert [(r["sub_type"], r["title"], r["url"], r["cite"], r["text"]) for r in rows] == [
        ("standard", "Paint Co", "/goto?url=p", "https://paint.test", "Free estimates.")
    ]


def test_local_place_ad_links_through_its_first_button():
    # A place-only ad has no data-pcu link: it is sub_type "place", the url is its
    # first action button ("Website"), and the "Why this ad?" whitespace is
    # stripped from the title.
    rows = parse_ads(
        comp(
            '<div data-text-ad="1"><div class="Tw0YHf">'
            '<div role="heading" aria-level="3"><span>Shop Name</span>'
            '<span><div role="button" aria-label="Why this ad?"> </div></span></div>'
            '<div class="aDWSGc"><span>Open late.</span></div>'
            '<div class="bn0HGf"><a href="https://www.google.com/aclk?site">Website</a>'
            '<a href="https://www.google.com/aclk?map">Directions</a></div>'
            "</div></div>"
        )
    )
    assert [(r["sub_type"], r["title"], r["url"], r["cite"], r["text"]) for r in rows] == [
        ("place", "Shop Name", "https://www.google.com/aclk?site", None, "Open late.")
    ]


def test_listing_carousel_rows_carry_the_vertical_heading():
    rows = parse_ads(
        comp(
            '<div class="GUyUUb"><span class="S3Mu6d">Sponsored tickets &amp; tours</span>'
            '<div role="list">'
            '<div role="listitem"><a class="KO2aMe" href="/goto?url=t1"></a>'
            '<div class="KZYtMc">Tower Ticket</div><div class="XO8mWb">$39</div>'
            '<div class="sX5I1c">TicketCo</div></div>'
            '<div role="listitem"><a class="KO2aMe" href="#"></a>'
            '<div class="KZYtMc">Harbor Hotel</div></div>'
            "</div></div>"
        )
    )
    heading = "Sponsored tickets & tours"
    assert rows == [
        {
            "type": "ad",
            "sub_type": "carousel",
            "sub_rank": 0,
            "title": "Tower Ticket",
            "url": "/goto?url=t1",
            "text": None,
            "cite": None,
            "details": {
                "type": "ratings",
                "price": "$39",
                "source": "TicketCo",
                "heading": heading,
            },
        },
        {
            # A "#" href is a script handler, not a destination.
            "type": "ad",
            "sub_type": "carousel",
            "sub_rank": 1,
            "title": "Harbor Hotel",
            "url": None,
            "text": None,
            "cite": None,
            "details": {"type": "item", "heading": heading},
        },
    ]


def test_vehicle_carousel_card():
    # The seller is a dealer name, not a display url: it stays in the text so a
    # consumer that reads ``cite`` as a url does not take it for one.
    rows = parse_ads(
        comp(
            '<g-scrolling-carousel><g-inner-card><a class="RtAwOe" href="/aclk?v"></a>'
            '<div class="avbHm"><h4 role="heading" aria-level="3">2026 Truck LT</h4><div></div>'
            "<div><span>$49,911</span></div><div><span>MSRP</span><span>$54,995</span></div>"
            '<div><span class="PWWaHb" role="text">Town Motors</span></div>'
            "<div><span>Springfield</span></div></div>"
            "</g-inner-card></g-scrolling-carousel>"
        )
    )
    assert [(r["title"], r["url"], r["cite"], r["text"]) for r in rows] == [
        ("2026 Truck LT", "/aclk?v", None, "$49,911 · MSRP $54,995 · Town Motors · Springfield")
    ]
