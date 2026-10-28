"""Targeted tests for parser-coverage fixes (plan 024).

Each test looks up curated SERPs by query in the consolidated ``serps.json.bz2``
fixture; these queries were selected to exercise specific parser gaps. Tests are
added per phase as the fixes land.
"""

import bz2
from pathlib import Path

import orjson
import pytest
from selectolax.lexbor import LexborNode as Node

import WebSearcher as ws
from WebSearcher import utils
from WebSearcher.classifiers.main import ClassifyMain
from WebSearcher.parsers.components.ai_overview import parse_ai_overview
from WebSearcher.parsers.components.datasets import parse_datasets
from WebSearcher.parsers.components.people_also_ask import parse_people_also_ask

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


def test_recipes_bare_header_level2():
    # The bare "Recipes" carousel heading also renders at aria-level 2, not only 3.
    assert _classify('<div aria-level="2" role="heading">Recipes</div>') == "recipes"


def test_recent_posts_from_entity_header():
    # "Posts from <entity>" is the same social carousel as "Latest posts from".
    assert (
        _classify('<div aria-level="2" role="heading">Posts from N2Shape</div>') == "recent_posts"
    )


def test_election_dates_level3_submodule():
    # Also renders as a level-3 entity-panel submodule ("Election dates - ...").
    inner = '<div aria-level="3" role="heading">Election dates · Primaries · Michigan</div>'
    assert _classify(inner) == "election_dates"


def test_places_nearby_carousel():
    from WebSearcher.parsers.components.places_nearby import parse_places_nearby

    inner = (
        '<div aria-level="2" role="heading"><span class="mgAbYb">Explore places nearby</span></div>'
        '<a href="#"><div aria-level="3" role="heading">Family Food Centre</div></a>'
        '<a href="#"><div aria-level="3" role="heading">Mega Mart</div></a>'
    )
    assert _classify(inner) == "places_nearby"
    node = _wrap(inner)
    rows = parse_places_nearby(node)
    assert [r["title"] for r in rows] == ["Family Food Centre", "Mega Mart"]
    assert all(r["url"] is None for r in rows)  # JS-driven cards, no static url


def test_top_stories_contextual_news_headers():
    # Contextual news-article carousels reuse the top_stories card parser.
    assert _classify('<div aria-level="2" role="heading">For context</div>') == "top_stories"
    assert _classify('<div aria-level="2" role="heading">States in the news</div>') == "top_stories"


def test_shopping_ideas_related_categories_nearby():
    # Local-shopping category chips render as a level-3 "Related categories nearby".
    inner = (
        '<div aria-level="3" role="heading">Related categories nearby</div>'
        '<a href="/search?q=shop+cheddar+near+me">Cheddar Cheese</a>'
        '<a href="/search?q=shop+swiss+near+me">Swiss Cheese</a>'
    )
    assert _classify(inner) == "shopping_ideas"


def test_gallery_structural():
    # Discovery gallery ("What to read"/"Courses"/...) typed by its Supercat attrid,
    # not the (varying, unregistered) heading. Parser emits a header row (heading +
    # joined category chips) then one row per item (title + author byline).
    from WebSearcher.parsers.components.gallery import parse_gallery

    inner = (
        '<div data-attrid="SupercatRecipeClusterTitle"></div>'
        '<div aria-level="2" role="heading">What to read</div>'
        '<div role="button" class="alvTwe">Law</div>'
        '<div role="button" class="alvTwe">Theory</div>'
        '<div><div class="sCqVCe">Book One</div><div class="kE4COc">Author A</div></div>'
        '<div style="display:none"><div class="sCqVCe">Book Two</div>'
        '<div class="kE4COc">Author B</div></div>'
    )
    assert _classify(inner) == "gallery"
    node = _wrap(inner)
    rows = parse_gallery(node)
    # header row: heading title + category chips joined into text
    assert rows[0]["sub_type"] == "header"
    assert rows[0]["title"] == "What to read"
    assert rows[0]["text"] == "Law<|>Theory"
    # item rows: sub_type="card" (mirrors twitter_cards header/card shape)
    assert [r["title"] for r in rows[1:]] == ["Book One", "Book Two"]
    assert [r["text"] for r in rows[1:]] == ["Author A", "Author B"]
    assert all(r["sub_type"] == "card" for r in rows[1:])
    assert all(r["url"] is None for r in rows[1:])
    # the shown card carries no visible flag; the display:none "More books" tail does
    assert rows[1].get("details") is None
    assert rows[2]["details"]["visible"] is False


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


def _wrap(inner: str) -> Node:
    node = utils.make_soup(f'<div class="wrap">{inner}</div>').css_first("div.wrap")
    assert node is not None
    return node


def _classify(inner: str) -> str:
    return ClassifyMain.classify(_wrap(inner))


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


def test_dictionary_panel_classifies_structurally_as_knowledge():
    # Left-bar/inline dictionary layout: no kp-blk/ULSxyf wrapper and the
    # "Dictionary" label is a non-heading span, so only the dob-modules container
    # identifies it. Must reach knowledge (not unknown) so _subtype_dictionary runs.
    cmpt_type = _classify(
        "<span>Dictionary</span>"
        '<div class="dob-modules"><span data-dobid="hdw">an·ti·pa·thy</span></div>'
    )
    assert cmpt_type == "knowledge"


def test_dictionary_panel_unknown_without_dob_modules():
    # A bare "Dictionary" span without the dob-modules container is not a
    # dictionary panel -- must not be claimed as knowledge by this rule.
    assert _classify('<span>Dictionary</span><div class="other">x</div>') != "knowledge"


def test_datasets_classifies_and_parses():
    # "Datasets" title is an aria-level-2 heading span (not h2/h3), read by
    # ClassifyMainHeader via the header_texts entry; each result is an h3 wrapped
    # in a source anchor.
    inner = (
        '<span aria-level="2" role="heading">Datasets</span>'
        '<a href="https://data.test/a"><h3>Global religion 2022</h3></a>'
        '<a href="https://data.test/b"><h3>Population by faith</h3></a>'
    )
    assert _classify(inner) == "datasets"
    node = _wrap(inner)
    rows = parse_datasets(node)
    assert len(rows) == 2
    assert rows[0]["title"] == "Global religion 2022"
    assert rows[0]["url"] == "https://data.test/a"


def test_recipes_async_popular_variant():
    # "Popular recipes" carousel: aria-level-2 heading (registered), and cards
    # where the title div sits outside the result anchor (XDOVcf wrapper).
    inner = (
        '<div aria-level="2" role="heading">Popular recipes</div>'
        '<div class="XDOVcf"><div class="hfac6d">Herb Batter Bread</div>'
        '<a href="https://food.test/herb">go</a></div>'
    )
    assert _classify(inner) == "recipes"
    node = _wrap(inner)
    from WebSearcher.parsers.components.recipes import parse_recipes

    rows = parse_recipes(node)
    assert len(rows) == 1
    assert rows[0]["title"] == "Herb Batter Bread"
    assert rows[0]["url"] == "https://food.test/herb"


def test_images_strip_classifies_and_parses():
    # Left-bar "Images" strip: offscreen a11y h3 "Images" label, no imagebox
    # signal; a thumbnail anchor + a caption anchor to the same url. Must reach
    # images end-of-chain and dedupe to one row keeping the text caption.
    inner = (
        '<h3 class="bNg8Rb">Images</h3>'
        '<a href="https://v.test/x"><img alt="thumb"></a>'
        '<a href="https://v.test/x">I See - YouTube</a>'
    )
    assert _classify(inner) == "images"
    node = _wrap(inner)
    from WebSearcher.parsers.components.images import parse_image_strip

    rows = parse_image_strip(node)
    assert len(rows) == 1
    assert rows[0]["title"] == "I See - YouTube"
    assert rows[0]["url"] == "https://v.test/x"


def test_refine_by_chips():
    # "Refine by <facet>" prefix-matched at aria-level 2; chips -> filtered search.
    from WebSearcher.parsers.components.refinements import parse_refine_by

    inner = (
        '<div aria-level="2" role="heading">Refine by color</div>'
        '<a href="/search?q=pink">Pink</a><a href="/search?q=blue">Blue</a>'
        '<a href="#">general feedback</a>'
    )
    assert _classify(inner) == "refine_by"
    node = _wrap(inner)
    rows = parse_refine_by(node)
    assert [r["title"] for r in rows] == ["Pink", "Blue"]  # feedback "#" chip skipped
    assert rows[0]["url"] == "/search?q=pink"
    # Product-category variant ("Refine <category>") is the same chip module.
    assert (
        _classify('<div aria-level="2" role="heading">Refine Wall Clocks &rsaquo; 24HR</div>')
        == "refine_by"
    )


def test_shopping_ideas_chips():
    from WebSearcher.parsers.components.refinements import parse_shopping_ideas

    inner = (
        '<div aria-level="2" role="heading">Shopping ideas</div>'
        '<a href="/search?q=jerseys">Jerseys</a><a href="/search?q=hats">Hats</a>'
    )
    assert _classify(inner) == "shopping_ideas"
    node = _wrap(inner)
    rows = parse_shopping_ideas(node)
    assert len(rows) == 2
    assert rows[0]["title"] == "Jerseys"


def test_articles_module():
    from WebSearcher.parsers.components.articles import parse_articles

    inner = (
        '<div aria-level="2" role="heading">Articles</div>'
        '<a href="https://pub.test/a"><img alt="thumb"></a>'
        '<a href="https://pub.test/a">Publisher Headline</a>'
        '<a href="#">general feedback</a>'
    )
    assert _classify(inner) == "articles"
    node = _wrap(inner)
    rows = parse_articles(node)
    assert len(rows) == 1  # deduped by url, feedback "#" skipped
    assert rows[0]["title"] == "Publisher Headline"
    assert rows[0]["url"] == "https://pub.test/a"


def test_knowledge_submodule_level3_menu_highlights():
    # "Menu highlights" renders its heading at aria-level 3 (not 2), so the
    # submodule rule must scan level 3 too.
    assert (
        _classify('<div aria-level="3" role="heading">Menu highlights</div><div>x</div>')
        == "knowledge"
    )


def test_knowledge_submodule_rooms_at_hotel():
    # "Rooms at <hotel>" room-rate module (aria-level 2) -> knowledge.
    assert (
        _classify('<div aria-level="2" role="heading">Rooms at Harris Guest House</div><img>')
        == "knowledge"
    )


def test_products_tray_carousel_level2_header():
    # "Popular products" / "More products" tray carousel titles its aria-level-2
    # g-tray-header span (not an h3), so the level-2 header_texts entry types it.
    assert _classify('<span aria-level="2" role="heading">Popular products</span>') == "products"
    assert _classify('<span aria-level="2" role="heading">More products</span>') == "products"


def test_knowledge_submodule_entity_tail_headings():
    # Standalone entity submodules splatted into the main column -> knowledge.
    for heading in (
        "Interactive diagrams",
        "Featured events",
        "How to solve your problem",
        "Top sights in Rome",
        "Beach destinations in Greece",
    ):
        assert _classify(f'<div aria-level="2" role="heading">{heading}</div><div>x</div>') == (
            "knowledge"
        ), heading


# --- ai_overview loading banner (crawl-6 unknowns) --------------------------
#
# SERPs serialized mid-generation ("Thinking") or after Google declined to
# synthesize an overview carry the EYwa3d controller but none of the
# Fzsovc/h2 markers. The same controller also lives inside knowledge panels
# embedding an AI-overview module, so the banner rule runs last in the chain
# and only claims otherwise-unknown components. These requests-backend
# captures never ran the script that streams the body in, so both decline
# messages are still hidden.

BANNER_QRYS = ["save your do , hair wrap", "moulinex a15453 760w toaster"]


@pytest.mark.parametrize("qry", BANNER_QRYS)
def test_ai_overview_banner_not_loaded(serps_by_qry, qry):
    rows = _rows(serps_by_qry[qry]["html"], "ai_overview")
    assert len(rows) == 1
    (row,) = rows
    assert row["sub_type"] == "not_loaded"
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


# --- ai_overview not loaded vs declined ---------------------------------------
#
# A browser capture taken before the overview streamed in, trimmed to its
# component. Each decline message sits in its own ``span.YWpX0d`` under an
# inline ``display:none``. No capture yet shows a decline; the declined case
# assumes the page's script removes that style from one message.

NOT_LOADED_FIXTURE = Path(__file__).parent / "fixtures" / "ai_overview_not_loaded.html"
_DECLINE_HIDDEN = 'jsname="lGsj1" class="YWpX0d" style="display:none"'


def _ai_overview_fixture(html: str, drop_css: str | None = None) -> dict:
    soup = utils.make_soup(html)
    if drop_css:
        for elem in soup.css(drop_css):
            elem.decompose()
    node = soup.css_first("div.bzXtMb")
    assert node is not None
    (row,) = parse_ai_overview(node)
    return row


def test_ai_overview_not_loaded_fixture():
    row = _ai_overview_fixture(NOT_LOADED_FIXTURE.read_text())
    assert row["sub_type"] == "not_loaded"
    assert row["text"] is None and row["details"] is None


def test_ai_overview_decline_shown():
    html = NOT_LOADED_FIXTURE.read_text()
    assert _DECLINE_HIDDEN in html
    row = _ai_overview_fixture(html.replace(_DECLINE_HIDDEN, 'jsname="lGsj1" class="YWpX0d"'))
    assert row["sub_type"] == "unavailable"
    assert row["text"] is None and row["details"] is None


def test_ai_overview_empty_without_messages_stays_flat():
    # No body and no decline messages: a parser miss, not a page state.
    row = _ai_overview_fixture(NOT_LOADED_FIXTURE.read_text(), drop_css="span.YWpX0d")
    assert row["sub_type"] == "flat"


@pytest.mark.parametrize("tag", ["script", "noscript", "style"])
def test_ai_overview_marker_in_unrendered_tag_not_a_decline(tag):
    # A marker string in unrendered text is not a shown message.
    root_open = '<div class="bzXtMb M8OgIe" jsname="Ya7sxe">'
    marker = "An AI Overview is not available for this search"
    html = NOT_LOADED_FIXTURE.read_text()
    assert html.startswith(root_open)
    row = _ai_overview_fixture(html.replace(root_open, f"{root_open}<{tag}>{marker}</{tag}>", 1))
    assert row["sub_type"] == "not_loaded"


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


# Knowledge-panel / image related-entity carousels: a level-2 heading over a row
# of ``a.ngTNl`` google.com/search?q= query links, identical in shape to the
# classic searches_related variants but with these heading labels. Registered as
# level-2 header_texts on ``searches_related`` (crawl-3 unknowns pass).
@pytest.mark.parametrize(
    "heading",
    [
        "Search instead for",
        "Other people search",
        "You can also search for",
        "People also search in Images",
    ],
)
def test_related_entity_carousel_headings(heading):
    inner = f'<div aria-level="2" role="heading">{heading}</div>'
    assert _classify(inner) == "searches_related"


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


# --- general: d4rhi host-group sub-results (plan 052) -----------------------
#
# Google stacks a "second result from the same host" as a div.d4rhi nested
# *inside* the div.g main result. find_subcomponents used to return on the
# div.g branch before reaching the d4rhi branch, so the nested sub-result was
# silently dropped -- no row, no parent details. It is now appended as its own
# indented general result (sub_type="indented"), the main result unchanged.

D4RHI_QRYS = ["abortion clinic", "how does abortion work"]


@pytest.mark.parametrize("qry", D4RHI_QRYS)
def test_general_d4rhi_indented_captured(serps_by_qry, qry):
    """Each d4rhi host-group sub-result surfaces as an indented general row."""
    indented = [
        r for r in _rows(serps_by_qry[qry]["html"], "general") if r["sub_type"] == "indented"
    ]
    assert indented, f"{qry}: no indented (d4rhi) general rows"
    for r in indented:
        assert r["sub_rank"] >= 1  # the main result of the group is sub_rank 0
        assert r["title"]
        assert r["url"] and r["url"].startswith("http")
        assert _row_error(r) is None


def test_general_d4rhi_specific_dropped_results_now_present(serps_by_qry):
    """The exact results from the plan-052 evidence -- previously dropped -- now
    appear as indented general rows."""
    clinic = _rows(serps_by_qry["abortion clinic"]["html"], "general")
    kalamazoo = [
        r for r in clinic if (r["title"] or "").startswith("Abortion Service in Kalamazoo")
    ]
    assert kalamazoo and kalamazoo[0]["sub_type"] == "indented"

    work = _rows(serps_by_qry["how does abortion work"]["html"], "general")
    titles = {(r["title"] or ""): r for r in work}
    for prefix in ("In-Clinic Abortion Procedure", "Abortion procedures - medication"):
        hit = next((r for t, r in titles.items() if t.startswith(prefix)), None)
        assert hit is not None, f"missing d4rhi result: {prefix}"
        assert hit["sub_type"] == "indented"


def test_general_d4rhi_main_result_kept_once(serps_by_qry):
    """Within each host-group component, the main result stays a single sub_rank-0
    row and the nested d4rhi is not double-counted (main url != indented url)."""
    rows = _rows(serps_by_qry["how does abortion work"]["html"], "general")
    indented_cmpts = {r["cmpt_rank"] for r in rows if r["sub_type"] == "indented"}
    assert indented_cmpts
    for cr in indented_cmpts:
        group = [r for r in rows if r["cmpt_rank"] == cr]
        mains = [r for r in group if r["sub_rank"] == 0]
        assert len(mains) == 1 and mains[0]["sub_type"] is None
        indented = [r for r in group if r["sub_type"] == "indented"]
        assert all(r["url"] != mains[0]["url"] for r in indented)  # not a duplicate of the main


# --- ai_overview role-heading layout (plan 060) ------------------------------
#
# The 2026-10 layout has no Fzsovc/h2: its "AI Overview" heading is a
# div[role=heading], and the body markup inside div.mZJni is renamed. These
# records were typed knowledge (via an embedded qTdDb controller) or reached
# ai_overview only through the banner rule and parsed empty. Keyed by serp_id:
# their queries repeat older corpus records.

AIO_ROLE_HEADING = {
    "ef30639b2b33": ["How It Works", "Why Sunsets Are Red"],  # why is the sky blue
    "adf0f7391ecc": 3,  # is it worth learning rust reddit (emoji-led headings)
    "42bc62be2985": ["Key Market Statistics"],  # aapl stock price, no sources
    # cheap flights to new york: typed by the banner rule, parsed empty
    "3765fb676f3c": ["Sample Fares & Routes (SFO to NYC)", "Best Time to Find Cheap Fares"],
}


@pytest.fixture(scope="module")
def serps_by_id():
    if not FIXTURE.exists():
        pytest.skip("parser-coverage fixture not available")
    return {r["serp_id"][:12]: r for r in _load()}


def _aio_row(serps_by_id, sid):
    rows = _rows(serps_by_id[sid]["html"], "ai_overview")
    assert len(rows) == 1
    return rows[0]


@pytest.mark.parametrize("sid", AIO_ROLE_HEADING)
def test_ai_overview_role_heading_sections(serps_by_id, sid):
    row = _aio_row(serps_by_id, sid)
    assert row["sub_type"] == "sectioned"
    assert row["text"]
    assert _row_error(row) is None
    sections = row["details"]["sections"]
    expected = AIO_ROLE_HEADING[sid]
    if isinstance(expected, int):
        assert len(sections) == expected
    else:
        assert [s["heading"] for s in sections] == expected
    assert all(s["text"] for s in sections)


@pytest.mark.parametrize("sid", AIO_ROLE_HEADING)
def test_ai_overview_role_heading_no_widget_leakage(serps_by_id, sid):
    """Citation labels and the closing follow-up prompt stay out of the text."""
    row = _aio_row(serps_by_id, sid)
    texts = [row["text"]] + [s["text"] for s in row["details"]["sections"]]
    labels = [
        f"{c['publisher']} +{c['additional_count']}"
        for c in _citations(row)
        if c["publisher"] and c["additional_count"]
    ]
    for text in texts:
        assert "Would you like" not in text
        assert not any(label in text for label in labels)


def _citations(row):
    details = row["details"]
    cites = list(details.get("citations", []))
    for section in details["sections"]:
        cites.extend(section.get("citations", []))
    return cites


def test_ai_overview_role_heading_citations_and_sources(serps_by_id):
    row = _aio_row(serps_by_id, "ef30639b2b33")
    details = row["details"]
    assert details["citations"] == [
        {"publisher": "NASA Space Place (.gov)", "additional_count": 0, "source_ids": ["1"]}
    ]
    sources = details["sources"]
    ids = [s["source_id"] for s in sources]
    assert len(ids) == len(set(ids)) == 7
    by_id = {s["source_id"]: s for s in sources}
    # Lead sources resolve from /goto redirects to the full URL; the rest keep
    # the redirect.
    assert by_id["1"]["url"] == "https://spaceplace.nasa.gov/blue-sky/"
    assert by_id["2_0"]["url"].startswith("/goto?url=")
    assert all(s["title"] and s["publisher"] for s in sources)
    # Every cited source id is in the tray.
    assert {i for c in _citations(row) for i in c["source_ids"]} <= set(ids)
    links = details["sections"][1]["hyperlinks"]
    assert links[0] == {"url": "https://spaceplace.nasa.gov/blue-sky/", "text": "NASA Space Place"}


def test_ai_overview_role_heading_follow_up(serps_by_id):
    """The closing follow-up prompt is its own detail, not part of the body text."""
    details = _aio_row(serps_by_id, "ef30639b2b33")["details"]
    assert details["follow_up"] == (
        "Would you like to know how particles like dust or pollution change the color "
        "of the sky, or how skies on other planets like Mars look?"
    )
    assert "follow_up" not in _aio_row(serps_by_id, "adf0f7391ecc")["details"]


def test_ai_overview_role_heading_in_body_source_panel(serps_by_id):
    """Some overviews list sources in a panel inside the body (div.fSJHKf)."""
    sources = _aio_row(serps_by_id, "adf0f7391ecc")["details"]["sources"]
    assert len(sources) == 14


def test_ai_overview_role_heading_without_sources(serps_by_id):
    assert "sources" not in _aio_row(serps_by_id, "42bc62be2985")["details"]


def test_ai_overview_role_heading_classifies_over_knowledge_controller():
    cmpt_type = _classify(
        '<div jscontroller="EYwa3d"><div role="heading">AI Overview</div>'
        '<div class="mZJni"><div class="n6owBd">Body</div>'
        '<div jscontroller="qTdDb"></div></div></div>'
    )
    assert cmpt_type == "ai_overview"


def test_ai_overview_role_heading_needs_controller():
    """People-also-ask answers embed div.mZJni without the EYwa3d controller."""
    assert _classify('<div class="mZJni"><div class="n6owBd">Body</div></div>') != "ai_overview"


def test_flight_search_widget_search_flights_heading(serps_by_id):
    """The es75Cc flight-search widget, now headed "Search flights", is typed flights."""
    html = serps_by_id["3765fb676f3c"]["html"]
    (row,) = [r for r in _rows(html, "flights") if r["title"] == "Search flights"]
    items = row["details"]["items"]
    assert len(items) == 4
    assert all(i["url"].startswith("https://www.google.com/travel/flights") for i in items)
    assert all(r["title"] or r["url"] for r in _rows(html, "general"))


# --- people_also_ask embedded AI overview answer (plan 061) -----------------
#
# In the 2026-10 layout the first PAA question ships its generated answer
# expanded, in the role-heading overview markup. It stays in the PAA row as
# details["answer"], and the row's sub_type is "ai_overview".

PAA_ANSWER = {
    # serp_id: (question, section headings, source count)
    "ef30639b2b33": ("Why is the sky blue a simple answer?", ["How It Works"], 7),
    "42bc62be2985": (
        "What is the price target for Apple?",
        ["Analyst Forecast Breakdown", "Recent Notable Price Target Updates"],
        5,
    ),
}


def _paa_row(serps_by_id, sid):
    (row,) = _rows(serps_by_id[sid]["html"], "people_also_ask")
    return row


def _answer_citations(answer):
    cites = list(answer.get("citations", []))
    for section in answer.get("sections", []):
        cites.extend(section.get("citations", []))
    return cites


@pytest.mark.parametrize("sid", PAA_ANSWER)
def test_paa_answer_fields(serps_by_id, sid):
    row = _paa_row(serps_by_id, sid)
    question, headings, n_sources = PAA_ANSWER[sid]
    assert row["sub_type"] == "ai_overview"
    assert _row_error(row) is None
    details = row["details"]
    assert details["type"] == "text"
    assert len(details["items"]) == 4  # the question list is unchanged
    answer = details["answer"]
    assert answer["question"] == question == details["items"][0]
    assert answer["text"]
    assert [s["heading"] for s in answer["sections"]] == headings
    assert all(s["text"] for s in answer["sections"])
    # Scoped to the question: the page's main overview has its own source cards.
    assert len(answer["sources"]) == n_sources


@pytest.mark.parametrize("sid", PAA_ANSWER)
def test_paa_answer_citations_and_leakage(serps_by_id, sid):
    answer = _paa_row(serps_by_id, sid)["details"]["answer"]
    cites = _answer_citations(answer)
    assert cites
    ids = {s["source_id"] for s in answer["sources"]}
    assert {i for c in cites for i in c["source_ids"]} <= ids
    labels = [
        f"{c['publisher']} +{c['additional_count']}"
        for c in cites
        if c["publisher"] and c["additional_count"]
    ]
    for text in [answer["text"]] + [s["text"] for s in answer["sections"]]:
        assert not any(label in text for label in labels)


def test_paa_answer_lede_citation(serps_by_id):
    answer = _paa_row(serps_by_id, "ef30639b2b33")["details"]["answer"]
    assert answer["citations"] == [
        {"publisher": "NASA Space Place (.gov)", "additional_count": 1, "source_ids": ["1", "9"]}
    ]


def _paa(inner):
    elem = utils.make_soup(f"<div><div>People also ask</div>{inner}</div>").css_first("div")
    assert elem is not None
    return parse_people_also_ask(elem)[0]


def test_paa_flat_answer():
    """An answer with no section headings is the lede alone."""
    row = _paa(
        '<div class="related-question-pair" data-q="Is it blue?">'
        '<div class="JlqpRe">Is it blue?</div>'
        '<div class="mZJni"><div class="n6owBd">Yes, it scatters blue light.</div></div></div>'
        '<div class="related-question-pair" data-q="Why?"><div class="JlqpRe">Why?</div></div>'
    )
    assert row["sub_type"] == "ai_overview"
    assert row["details"] == {
        "type": "text",
        "items": ["Is it blue?", "Why?"],
        "answer": {"question": "Is it blue?", "text": "Yes, it scatters blue light."},
    }


def test_paa_without_answer():
    row = _paa(
        '<div class="related-question-pair" data-q="Why?"><div class="JlqpRe">Why?</div></div>'
        '<div class="mZJni"><div class="n6owBd">Outside any question.</div></div>'
    )
    assert row["sub_type"] is None
    assert row["details"] == {"type": "text", "items": ["Why?"]}


def test_paa_answer_bounded_to_question_pairs():
    """An overview outside every question pair is not bound to an outer ``data-q``."""
    html = (
        '<div data-q="Outer question"><div id="paa"><div>People also ask</div>'
        '<div class="related-question-pair" data-q="Why?"><div class="JlqpRe">Why?</div></div>'
        '<div class="mZJni"><div class="n6owBd">Outside any question.</div></div>'
        "</div></div>"
    )
    elem = utils.make_soup(html).css_first("div#paa")
    assert elem is not None
    row = parse_people_also_ask(elem)[0]
    assert row["sub_type"] is None
    assert row["details"] == {"type": "text", "items": ["Why?"]}


# --- 2026-10 layouts (plan 063) ----------------------------------------------
#
# Fixtures from a 2026-10 crawl batch parsed with 0.12.1, where top stories and
# text ads returned "no subcomponents parsed", the AI-overview banner arrived
# wrapped in the qTdDb knowledge controller, and the Featured results band
# (role=group) reached unknown.

TOP_STORIES_2026_10 = {
    "virginia tech vs west virginia": 3,  # vertical list
    "jenna ortega": 7,  # div.MmyPhf clusters + "Also in the news"
}


@pytest.mark.parametrize("qry", TOP_STORIES_2026_10)
def test_top_stories_2026_10_cards(serps_by_qry, qry):
    rows = _rows(serps_by_qry[qry]["html"], "top_stories")
    assert len(rows) == TOP_STORIES_2026_10[qry]
    for row in rows:
        assert row["title"] and row["url"] and row["cite"], row
        assert _row_error(row) is None
        assert row["details"]["timestamp"].endswith("ago")


def test_text_ads_2026_10(serps_by_qry):
    rows = _rows(serps_by_qry["chargers vs raiders"]["html"], "ad")
    assert [r["cite"] for r in rows] == ["https://www.viagogo.com", "https://www.tickpick.com"]
    for row in rows:
        assert row["sub_type"] == "submenu"
        assert row["title"] and row["url"] and row["text"]
        assert row["text"] != row["title"]
        assert row["details"]["items"]


def test_text_ad_mid_page_block(serps_by_qry):
    results = ws.parse_serp(serps_by_qry["ceiling chandelier"]["html"])["results"]
    ads = [r for r in results if r["type"] == "ad"]
    assert len(ads) == 1 and ads[0]["title"] and _row_error(ads[0]) is None
    assert not [r for r in results if r["type"] == "unknown"]


@pytest.mark.parametrize("qry", ["solitair1lalakakwwowoows9owpalqlsaeu5l", "chargers vs raiders"])
def test_ai_overview_wrapped_banner(serps_by_qry, qry):
    results = ws.parse_serp(serps_by_qry[qry]["html"])["results"]
    assert (results[0]["type"], results[0]["sub_type"]) == ("ai_overview", "not_loaded")
    empty_panels = [
        r for r in results if r["type"] == "knowledge" and not (r["title"] or r["text"] or r["url"])
    ]
    assert not empty_panels


_BANNER = (
    '<div jscontroller="EYwa3d"><span>An AI Overview is not available for this search</span>'
    '<div role="heading" aria-level="2"><span>Thinking</span></div></div>'
)


def test_wrapped_banner_classifies_as_ai_overview():
    cmpt_type = _classify(
        f'<div jscontroller="qTdDb"><div class="hdzaWe">{_BANNER}</div></div>'
        '<div jscontroller="qTdDb"></div>'
    )
    assert cmpt_type == "ai_overview"


def test_knowledge_panel_embedding_banner_stays_knowledge():
    # Panel content beside the banner inside the qTdDb wrapper.
    assert (
        _classify(f'<div jscontroller="qTdDb"><div>Barack Obama</div>{_BANNER}</div>')
        == "knowledge"
    )
    # Another knowledge-panel marker outside the wrapper.
    assert (
        _classify(f'<div class="kp-blk">Obama</div><div jscontroller="qTdDb">{_BANNER}</div>')
        == "knowledge"
    )


def test_featured_results_group_band(serps_by_qry):
    rows = _knowledge(serps_by_qry['"the car" movie']["html"], "featured_results")
    kinds = [r["details"]["kind"] for r in rows]
    assert kinds[0] == "video" and "description" in kinds
    assert rows[0]["title"].startswith("The Car Official Trailer")
    assert rows[0]["text"].startswith("YouTube")


def test_featured_results_group_band_classifies_as_knowledge():
    assert (
        _classify(
            '<div role="group" aria-label="Featured results">'
            '<div data-attrid="VisualDigestDescription">Source: IMDb</div></div>'
        )
        == "knowledge"
    )


def test_bracket_module_is_knowledge(serps_by_qry):
    results = ws.parse_serp(serps_by_qry["fifa finals bracket"]["html"])["results"]
    assert not [r for r in results if r["type"] == "unknown"]


@pytest.mark.parametrize(
    ("qry", "heading"),
    [
        ("chicopee woods golf course", "Reserve a tee time"),
        ("juliana-hairstylist-beautician", "Book an appointment"),
    ],
)
def test_booking_widget_is_knowledge(serps_by_qry, qry, heading):
    results = ws.parse_serp(serps_by_qry[qry]["html"])["results"]
    assert not [r for r in results if r["type"] == "unknown"]
    headings = [(r["details"] or {}).get("heading") or "" for r in _rows_of(results, "knowledge")]
    assert sum(h.startswith(heading) for h in headings) == 1


def _rows_of(results, type_):
    return [r for r in results if r["type"] == type_]


@pytest.mark.parametrize(
    ("qry", "n_ads", "linked"),
    [
        ("suwanee-painters", 2, True),  # text ad with a place card + a plain text ad
        ("sydney rosen company, 714 sansom st, philadelphia, pa 19106", 2, True),  # place ads
        ("lochmandy elkhart", 3, True),  # vehicle carousel
        ("astronomical clocks czech republic", 8, True),  # tickets & tours listings
        ("bora bora resort", 7, False),  # hotel listings link to "#"
    ],
)
def test_2026_10_ad_variants_parse(serps_by_qry, qry, n_ads, linked):
    ads = _rows_of(ws.parse_serp(serps_by_qry[qry]["html"])["results"], "ad")
    assert len(ads) == n_ads
    for ad in ads:
        assert ad["title"] and _row_error(ad) is None
        assert (ad["url"] is not None) is linked
        assert ad["text"] or (ad["details"] or {}).get("price")


def test_featured_results_fact_keeps_full_value(serps_by_qry):
    rows = _knowledge(serps_by_qry["albert einstein"]["html"], "featured_results")
    facts = {
        r["details"]["label"]: r["details"]["value"] for r in rows if r["details"]["kind"] == "fact"
    }
    assert facts["Born"] == "Mar 14, 1879 · Ulm, Germany"
    assert facts["Died"] == "Apr 18, 1955 · Princeton, NJ"


def test_text_ad_rule_leaves_related_products_ads_to_searches_related():
    # "Find related products & services" embeds a "Sponsored results" unit;
    # searches_related (typed by its heading earlier in the chain) emits the ads.
    cmpt_type = _classify(
        '<span class="L8u9l" role="heading" aria-level="2">Sponsored results</span>'
        '<div class="uEierd"><div data-text-ad="1"><div role="heading">Ad</div></div></div>'
        '<div role="heading" aria-level="2">Find related products &amp; services</div>'
    )
    assert cmpt_type == "searches_related"
    assert _classify('<div data-text-ad="1"><div role="heading">Ad</div></div>') == "ad"


def test_wrapped_banner_rule_needs_the_controller():
    # A qTdDb wrapper with no EYwa3d banner is a knowledge panel.
    node = _wrap('<div jscontroller="qTdDb"><div>Thinking</div></div>')
    assert ClassifyMain.ai_overview_wrapped_banner(node) == "unknown"
    assert ClassifyMain.classify(node) == "knowledge"


def _story(age_html: str) -> dict:
    from WebSearcher.parsers.components.top_stories import parse_top_story

    html = f'<a class="aJWbwf" href="/s"><div class="n0jPhd">T</div>{age_html}</a>'
    node = utils.make_soup(html).css_first("a.aJWbwf")
    assert node is not None
    return parse_top_story(node, "top_stories")


def test_top_story_age_skips_video_label():
    video = '<div class="OSrXXb"><span class="Uz7khf">Video</span><span>24 hours ago</span></div>'
    assert _story(video)["details"]["timestamp"] == "24 hours ago"
    label_only = '<div class="OSrXXb"><span class="Uz7khf">Video</span></div>'
    assert _story(label_only).get("details") is None
    nested = '<div class="OSrXXb"><span><span>3</span> days ago</span></div>'
    assert _story(nested)["details"]["timestamp"] == "3 days ago"
