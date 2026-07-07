"""Targeted tests for parser-coverage fixes (plan 024).

Each test looks up curated SERPs by query in the consolidated ``serps.json.bz2``
fixture; these queries were selected to exercise specific parser gaps. Tests are
added per phase as the fixes land.
"""

import bz2
from pathlib import Path

import orjson
import pytest

import WebSearcher as ws
from WebSearcher import utils
from WebSearcher.classifiers.main import ClassifyMain

FIXTURE = Path(__file__).parent / "fixtures" / "serps.json.bz2"


def _load():
    with bz2.open(FIXTURE, "rt") as f:
        return [orjson.loads(line) for line in f]


@pytest.fixture(scope="module")
def serps_by_qry():
    if not FIXTURE.exists():
        pytest.skip("parser-coverage fixture not available")
    return {r["qry"]: r for r in _load()}


def _rows(html, type_):
    return [r for r in ws.parse_serp(html)["results"] if r["type"] == type_]


def _row_error(r: dict) -> str | None:
    """Parse error for a result row -- nested in ``details`` (two-tier schema)."""
    details = r.get("details")
    return details.get("error") if isinstance(details, dict) else None


# --- recipes (phase 2) -----------------------------------------------------

RECIPE_QRYS = ["birthday cake with candles", "biscuit and gravy recipe"]


@pytest.mark.parametrize("qry", RECIPE_QRYS)
def test_recipes_structured(serps_by_qry, qry):
    rows = _rows(serps_by_qry[qry]["html"], "recipes")
    assert rows, f"{qry}: no recipe cards parsed"
    for r in rows:
        # title + url recovered, no <|>-joined blob, no not-implemented error
        assert r["title"]
        assert r["url"] and r["url"].startswith("http")
        assert "<|>" not in (r["text"] or "")
        assert _row_error(r) is None
        # structured metadata reusing the ratings details type
        details = r["details"]
        assert details is not None and details["type"] == "ratings"
        assert details.get("source")


# --- knowledge: empty sub_types (phase 3) ----------------------------------


def _knowledge(html, sub_type):
    return [
        r
        for r in ws.parse_serp(html)["results"]
        if r["type"] == "knowledge" and r.get("sub_type") == sub_type
    ]


@pytest.mark.parametrize(
    "qry", ["mater (cars)", "pitbull i believe that we will win (world anthem)"]
)
def test_knowledge_featured_results(serps_by_qry, qry):
    rows = _knowledge(serps_by_qry[qry]["html"], "featured_results")
    assert rows
    # recovers text + an absolute source url (was entirely empty before)
    assert any(r["text"] and r["url"] and r["url"].startswith("http") for r in rows)


@pytest.mark.parametrize("qry", ["cistern", "define judgement"])
def test_knowledge_dictionary(serps_by_qry, qry):
    rows = _knowledge(serps_by_qry[qry]["html"], "dictionary")
    assert rows
    row = rows[0]
    # headword + definition text recovered (was entirely empty before)
    assert row["title"]
    assert row["text"] and len(row["text"]) > 20


# --- side_bar: RHS column panel (type renamed knowledge -> side_bar) --------


def _side_bar(html, sub_type):
    return [
        r
        for r in ws.parse_serp(html)["results"]
        if r["type"] == "side_bar" and r.get("sub_type") == sub_type
    ]


@pytest.mark.parametrize("qry", ["prouve", "red skin peanuts", "file folder"])
def test_side_bar_panel_not_empty(serps_by_qry, qry):
    rows = _side_bar(serps_by_qry[qry]["html"], "panel")
    assert rows
    for r in rows:
        # no longer a hollow placeholder: has a title and/or text and/or details
        assert r["title"] or r["text"] or r["details"]


def test_side_bar_panel_entity_title(serps_by_qry):
    """Entity panels recover their title from the data-attrid (was empty)."""
    row = _side_bar(serps_by_qry["prouve"]["html"], "panel")[0]
    assert row["title"] == "Jean Prouvé"
    assert row["text"] and row["url"]


# --- twitter_cards: legacy card title (phase 4) ----------------------------


@pytest.mark.parametrize("qry", ["movement", "oscar the grouch"])
def test_twitter_card_title_from_handle(serps_by_qry, qry):
    rows = [
        r
        for r in ws.parse_serp(serps_by_qry[qry]["html"])["results"]
        if r["type"] == "twitter_cards" and r.get("sub_type") == "card"
    ]
    assert rows
    for r in rows:
        # single-account carousel: title recovered as the author handle (@...)
        assert r["title"] and r["title"].startswith("@")
        assert r["text"]  # tweet body still extracts
        assert r["url"]


# --- shopping_ads: modern PLA cards (phase 5) ------------------------------


@pytest.mark.parametrize("qry", ["drawing tablet", "kelly kettle"])
def test_shopping_ads_modern_pla(serps_by_qry, qry):
    rows = _rows(serps_by_qry[qry]["html"], "shopping_ads")
    # modern clickable-card layout: multiple products, each with title + url
    assert len(rows) > 1
    for r in rows:
        assert r["title"]
        assert r["url"]
        assert _row_error(r) is None
        # price/source captured in a ratings details block
        assert r["details"] is None or r["details"]["type"] == "ratings"


# --- products: organic shopping packs out of general (plan 025) -------------


def _hollow_general(html):
    return [
        r
        for r in ws.parse_serp(html)["results"]
        if r["type"] == "general"
        and all(r[k] is None for k in ("sub_type", "title", "url", "text", "cite"))
    ]


def test_products_no_hollow_general(serps_by_qry):
    """The shopping packs no longer leak hollow rows into general."""
    assert _hollow_general(serps_by_qry["men's old school wears"]["html"]) == []


def test_products_brands_carousel(serps_by_qry):
    """'Explore brands' carousel: each merchant card has a title + merchant url."""
    rows = [
        r
        for r in _rows(serps_by_qry["men's old school wears"]["html"], "products")
        if r["sub_type"] == "brands"
    ]
    assert len(rows) > 1
    for r in rows:
        assert r["title"]
        assert r["url"] and r["url"].startswith("http")
        assert _row_error(r) is None
        assert r["details"] is None or r["details"]["type"] == "ratings"


def test_products_grid(serps_by_qry):
    """Immersive product grid: title + store, price/rating in ratings details."""
    rows = [
        r
        for r in _rows(serps_by_qry["men's old school wears"]["html"], "products")
        if r["sub_type"] == "grid"
    ]
    assert len(rows) > 1
    for r in rows:
        assert r["title"]  # product name (no url: JS-driven cards)
        assert _row_error(r) is None
    # at least some grid cards carry a structured price
    assert any(r["details"] and r["details"].get("price") for r in rows)


@pytest.mark.parametrize("qry", ["red skin peanuts", "file folder", "kelly kettle"])
def test_products_grid_older_markup(serps_by_qry, qry):
    """Older product grids (product-viewer-group + g-inner-card, no
    apg-product-result) also route to products/grid with no hollow rows."""
    assert _hollow_general(serps_by_qry[qry]["html"]) == []
    rows = [r for r in _rows(serps_by_qry[qry]["html"], "products") if r["sub_type"] == "grid"]
    assert len(rows) > 1
    for r in rows:
        assert r["title"]
        assert _row_error(r) is None


def test_general_image_strip_subtype(serps_by_qry):
    """General results with a g-img thumbnail strip get sub_type=image_strip,
    while keeping their title + url (pure enrichment, no hollow rows)."""
    rows = [
        r
        for r in _rows(serps_by_qry["men's old school wears"]["html"], "general")
        if r["sub_type"] == "image_strip"
    ]
    assert len(rows) > 1
    for r in rows:
        assert r["title"]
        assert r["url"] and r["url"].startswith("http")
        assert _row_error(r) is None


# --- promo / most_read_articles / buying_guide (plan 025) ------------------


@pytest.mark.parametrize("qry", ["men's old school wears", "drawing tablet"])
def test_promo_shopping_banner(serps_by_qry, qry):
    """The 'Save with deals / Shop deals' banner is captured as promo/shopping."""
    rows = _rows(serps_by_qry[qry]["html"], "promo")
    assert len(rows) == 1
    r = rows[0]
    assert r["sub_type"] == "shopping"
    assert r["title"] and "deals" in r["title"].lower()
    assert r["text"]  # CTA label
    assert _row_error(r) is None


def test_most_read_articles(serps_by_qry):
    """Most-read articles carousel: each card has a title + article url."""
    rows = _rows(serps_by_qry["drawing tablet"]["html"], "most_read_articles")
    assert len(rows) > 1
    for r in rows:
        assert r["title"]
        assert r["url"] and r["url"].startswith("http")
        assert _row_error(r) is None


def test_buying_guide(serps_by_qry):
    """Buying guide accordion: each facet has a label (title) + question (text)."""
    rows = _rows(serps_by_qry["drawing tablet"]["html"], "buying_guide")
    assert len(rows) > 1
    for r in rows:
        assert r["title"]  # facet label
        assert r["text"]  # facet question/value
        assert _row_error(r) is None


# --- structural-first dispatch (plan 040) ----------------------------------
#
# buying_guide (ITWcLb) and products/brands (gON1yc) carry unique structural CSS
# signals, so they classify even when their English headers are localized or
# reworded -- the header-text path alone would miss those. most_read_articles
# has no such signal and stays header-text-only (documented, not fixed).


def _classify(inner: str) -> str:
    return ClassifyMain.classify(
        utils.make_soup(f'<div class="wrap">{inner}</div>').css_first("div.wrap")
    )


def test_buying_guide_classifies_structurally_without_english_header():
    # Localized heading ("Buying guide" not matched), only the ITWcLb row class.
    cmpt_type = _classify(
        '<div role="heading">Guia de compra</div><div class="ITWcLb">Tablets: cual?</div>'
    )
    assert cmpt_type == "buying_guide"


def test_buying_guide_unknown_without_structural_signal():
    # No ITWcLb and no matching header -> not a buying_guide.
    assert (
        _classify('<div role="heading">Guia de compra</div><div>Tablets: cual?</div>')
        != "buying_guide"
    )


def test_products_brands_classifies_structurally_without_english_header():
    # Localized heading ("Explore brands" not matched), only the gON1yc card class
    # and no g-more-link/product-viewer-group gate -- must still reach products.
    cmpt_type = _classify(
        '<div role="heading">Explorar marcas</div>'
        '<div class="gON1yc"><a class="J0tlkf" href="https://x.test">Marca</a></div>'
    )
    assert cmpt_type == "products"


def test_most_read_articles_has_no_structural_fallback():
    # Localized heading + generic card classes: header-text-only type is
    # unclassifiable without the English "Most-read articles" heading.
    assert (
        _classify('<div role="heading">Articulos mas leidos</div><div class="EDblX">card</div>')
        == "unknown"
    )


# --- ai_overview unavailable banner (crawl-6 unknowns) ----------------------
#
# SERPs serialized mid-generation ("Thinking") or after Google declined to
# synthesize an overview carry the EYwa3d controller but none of the
# Fzsovc/h2 markers. The same controller also lives inside knowledge panels
# embedding an AI-overview module, so the banner rule runs last in the chain
# and only claims otherwise-unknown components.

BANNER_QRYS = ["save your do , hair wrap", "moulinex a15453 760w toaster"]


@pytest.mark.parametrize("qry", BANNER_QRYS)
def test_ai_overview_banner_unavailable(serps_by_qry, qry):
    rows = _rows(serps_by_qry[qry]["html"], "ai_overview")
    assert len(rows) == 1
    (row,) = rows
    assert row["sub_type"] == "unavailable"
    assert row["title"] is None and row["url"] is None and row["text"] is None
    assert _row_error(row) is None


def test_ai_overview_banner_classifies_on_controller():
    cmpt_type = _classify(
        '<div class="hdzaWe"><div jscontroller="EYwa3d">'
        "<span>An AI Overview is not available for this search</span></div></div>"
    )
    assert cmpt_type == "ai_overview"


def test_ai_overview_banner_unknown_without_controller():
    assert (
        _classify(
            '<div class="hdzaWe"><span>An AI Overview is not available for this search</span></div>'
        )
        == "unknown"
    )


# --- crawl-6 unknown submodules (second pass) --------------------------------
#
# Standalone knowledge-panel submodules, hotel carousels, advertiser suggestion
# lists, and widget variants that Google splats into the main column. Each was
# an ``unknown`` (or hollow ``general``/``knowledge`` panel) before the
# crawl-6-unknowns pass.


def test_related_products_services_suggestions(serps_by_qry):
    # Advertiser suggestion module: query links land in items, not a text blob.
    rows = [
        r
        for r in _rows(serps_by_qry["hotels polaris ohio"]["html"], "searches_related")
        if r["sub_type"] == "find_related_products_&_services"
    ]
    assert len(rows) == 1
    (row,) = rows
    assert row["details"]["items"]
    assert all("<|>" not in item for item in row["details"]["items"])
    assert _row_error(row) is None


def test_recent_posts_level3_heading(serps_by_qry):
    # "Latest posts from <entity>" with an aria-level-3 heading.
    rows = _rows(serps_by_qry["twitter inc."]["html"], "recent_posts")
    assert rows
    assert any(r["url"] and "x.com" in r["url"] for r in rows)


def test_hotel_card_carousel(serps_by_qry):
    # "Similar to <hotel>" / "Popular hotels in <place>" JS-hydrated cards.
    rows = _rows(serps_by_qry["seven feathers casino"]["html"], "locations")
    assert rows
    for r in rows:
        assert r["sub_type"] == "hotels"
        assert r["title"]
        assert r["url"] and "/local/places/hotel/" in r["url"]
        assert _row_error(r) is None


def test_more_hotels_split_heading(serps_by_qry):
    # "More Hotels" heading split across spans ("More" + "Hotels").
    rows = _rows(serps_by_qry["hotels polaris ohio"]["html"], "locations")
    assert rows
    for r in rows:
        assert r["sub_type"] == "hotels"
        assert r["title"]
        assert r["url"] and "/travel/search" in r["url"]


KNOWLEDGE_SUBMODULE_QRYS = [
    "قطريات",  # "Things to do" heading branch
    "johnny drama",  # lab/title + lab/content attrid branch
    "ukrainian minister of interior",  # CoreAnswerModuleHeader breadcrumb
    "women's world cup 2019 schedule",  # TLOsrpMatchListSummary sports module
    "portugal world cup squad",  # sp-table squad table
]


@pytest.mark.parametrize("qry", KNOWLEDGE_SUBMODULE_QRYS)
def test_knowledge_submodule_claims_component(serps_by_qry, qry):
    parsed = ws.parse_serp(serps_by_qry[qry]["html"])["results"]
    assert any(r["type"] == "knowledge" for r in parsed)
    assert not any(r["type"] == "unknown" for r in parsed)


def test_flight_status_bare_h2(serps_by_qry):
    rows = _rows(serps_by_qry["american1967"]["html"], "flights")
    assert len(rows) == 1
    assert rows[0]["title"] == "Flight status"


def test_knowledge_submodule_classifies_on_lab_attrid():
    assert _classify('<div data-attrid="lab/title/Movies"><span>Movies</span></div>') == "knowledge"


def test_knowledge_submodule_heading_needs_registered_text():
    # Same markup shape, unregistered heading text: stays unknown.
    assert (
        _classify('<div aria-level="2" role="heading"><span>Menu highlights</span></div>')
        == "knowledge"
    )
    assert (
        _classify('<div aria-level="2" role="heading"><span>Unregistered heading</span></div>')
        == "unknown"
    )


def test_hotel_carousel_classifies_on_places_anchor():
    assert (
        _classify('<a href="https://search.google.com/local/places/hotel/navigational?q=x">h</a>')
        == "locations"
    )


def test_locations_space_joined_heading():
    # "More" + "Hotels" in separate spans previously read "MoreHotels".
    assert (
        _classify('<div role="heading"><span>More</span> <span>Hotels</span></div>') == "locations"
    )


def test_ad_sitelinks_ynawrc_format(serps_by_qry):
    # Format-3 sitelinks: bare a.ynAwRc anchors (no MhgNwc/bOeY0b wrapper).
    rows = _rows(serps_by_qry["best mattress forum"]["html"], "ad")
    submenu = [r for r in rows if r["sub_type"] == "submenu"]
    assert submenu
    for r in submenu:
        items = r["details"]["items"]
        assert items
        assert all(it["title"] and it["url"] for it in items)


def test_find_related_embedded_sponsored_ads(serps_by_qry):
    # The module's "Sponsored results" unit emits ad rows ahead of the
    # suggestions row, inside the same component.
    results = ws.parse_serp(serps_by_qry["car insurance quotes"]["html"])["results"]
    cmpt = [
        r
        for r in results
        if r["type"] == "searches_related" and r["sub_type"] == "find_related_products_&_services"
    ]
    assert len(cmpt) == 1
    cmpt_rank = cmpt[0]["cmpt_rank"]
    ads = [r for r in results if r["cmpt_rank"] == cmpt_rank and r["type"] == "ad"]
    assert ads
    for r in ads:
        assert r["title"] and r["url"]
        assert r["sub_rank"] < cmpt[0]["sub_rank"]
