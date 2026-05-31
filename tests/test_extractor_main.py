"""Tests for ExtractorMain component validity filtering and layout dispatch."""

from WebSearcher import utils
from WebSearcher._slx import get_text
from WebSearcher.components import ComponentList
from WebSearcher.extractors.extractor_main import ExtractorMain, _find_all_with_class


def comp(html: str):
    """Build a single component ``Node`` from an HTML fragment."""
    return utils.make_soup(f'<div class="wrap">{html}</div>').css_first("div.wrap")


def _texts(nodes) -> list[str]:
    return [(get_text(n) or "").strip() for n in nodes]


def _make_extractor(body: str, *, top_bars_css: str | None = None) -> ExtractorMain:
    """Build an ExtractorMain over ``body`` with layout_divs primed as
    ``get_layout`` would set them (rso + optional top-bars)."""
    soup = utils.make_soup(f"<html><body>{body}</body></html>")
    em = ExtractorMain(soup, ComponentList())
    em.layout_divs["rso"] = soup.css_first('div[id="rso"]')
    em.layout_divs["left-bar"] = soup.css_first("div.OeVqAd")
    rcnt = soup.css_first('div[id="rcnt"]')
    em.layout_divs["top-bars"] = (
        _find_all_with_class(rcnt, top_bars_css) if (rcnt is not None and top_bars_css) else []
    )
    return em


def _layout_label(body: str) -> str | None:
    soup = utils.make_soup(f"<html><body>{body}</body></html>")
    em = ExtractorMain(soup, ComponentList())
    em.get_layout()
    return em.layout_label


# is_valid: bad-label / empty rejection ----------------------------------------


def test_is_valid_rejects_falsy():
    assert ExtractorMain.is_valid(None) is False


def test_is_valid_rejects_bad_label():
    # Exact bad-label match (within the 15-char scan bound) is dropped.
    assert ExtractorMain.is_valid(comp("Main results")) is False
    assert ExtractorMain.is_valid(comp("Twitter Results")) is False


def test_is_valid_keeps_normal_component():
    assert ExtractorMain.is_valid(comp("A normal result with plenty of text")) is True


def test_is_valid_rejects_bottom_ads_wrapper():
    assert ExtractorMain.is_valid(comp('<div id="tadsb">bottom ads</div>')) is False


# is_valid: promo-throttler filter ---------------------------------------------
# A ULSxyf wrapping a promo-throttler is dropped only when it ALSO holds organic
# results (div.g) -- the redundant main-results wrapper whose results are
# extracted individually elsewhere. A pure promo banner (no div.g, e.g. the
# "Save with deals / Shop deals" CTA) is kept and classified as `promo`.


def test_is_valid_drops_promo_results_wrapper():
    # ULSxyf + promo-throttler + div.g -> redundant results wrapper, dropped.
    ulsxyf = utils.make_soup(
        '<div class="ULSxyf"><promo-throttler></promo-throttler>'
        '<div class="g">a web result</div></div>'
    ).css_first("div.ULSxyf")
    assert ExtractorMain.is_valid(ulsxyf) is False


def test_is_valid_keeps_promo_banner():
    # ULSxyf + promo-throttler, no div.g -> pure promo banner, kept for `promo`.
    ulsxyf = utils.make_soup(
        '<div class="ULSxyf">Save with deals<promo-throttler></promo-throttler></div>'
    ).css_first("div.ULSxyf")
    assert ExtractorMain.is_valid(ulsxyf) is True


def test_is_valid_keeps_ulsxyf_without_throttler():
    ulsxyf = utils.make_soup('<div class="ULSxyf">A knowledge block, not a survey</div>').css_first(
        "div.ULSxyf"
    )
    assert ExtractorMain.is_valid(ulsxyf) is True


def test_is_valid_keeps_throttler_without_ulsxyf():
    other = utils.make_soup(
        '<div class="other">content<promo-throttler></promo-throttler></div>'
    ).css_first("div.other")
    assert ExtractorMain.is_valid(other) is True


# get_layout: routing-label truth table ----------------------------------------
# Pins which of the four extractor keys get_layout selects for each (top-bars,
# left-bar, rso) combination. These are the registry keys; the chosen extractor
# may further mutate layout_label (see standard-*/top-bars-* tests below).

_RCNT_TOPBAR = '<div id="rcnt"><div class="XqFnDf">bar</div></div>'


def test_get_layout_label_standard_for_rso_only():
    assert _layout_label('<div id="rso"></div>') == "standard"


def test_get_layout_label_no_rso_when_rso_absent():
    assert _layout_label("<div>nothing</div>") == "no-rso"


def test_get_layout_label_left_bar_takes_precedence_over_rso():
    # A left-bar marker wins even when rso is present -- rso is then never read.
    assert _layout_label('<div class="OeVqAd"></div><div id="rso"></div>') == "left-bar"


def test_get_layout_label_top_bars_folds_into_standard_with_rso():
    assert _layout_label(f'{_RCNT_TOPBAR}<div id="rso"></div>') == "standard"


def test_get_layout_label_top_bars_without_rso():
    assert _layout_label(_RCNT_TOPBAR) == "top-bars"


def test_get_layout_label_top_bars_takes_precedence_over_left_bar():
    # layouts dict order is top-bars, left-bar, standard, no-rso and the first
    # truthy flag wins -- so a populated top-bar outranks a left-bar marker.
    assert _layout_label(f'{_RCNT_TOPBAR}<div class="OeVqAd"></div>') == "top-bars"


# extract_from_standard: standard-* sub-type dispatch --------------------------
# standard-overview and standard-airfares are witnessed by fixtures;
# standard-songs and standard-sports-standings are NOT, so they are pinned here.


def test_standard_overview_extracts_tzhb6b_children():
    em = _make_extractor(
        '<div id="rso"><div id="kp-wp-tab-overview">'
        '<div class="TzHB6b">ov 1</div><div class="TzHB6b">ov 2</div>'
        "</div></div>"
    )
    res = em.extract_from_standard()
    assert em.layout_label == "standard-overview"
    assert _texts(res) == ["ov 1", "ov 2"]


def test_standard_songs_extracts_tab_children():
    em = _make_extractor(
        '<div id="rso">'
        '<div id="kp-wp-tab-cont-Songs" role="tabpanel"><div>tabwrap</div></div>'
        '<div id="kp-wp-tab-Songs"><div>song A</div><div>song B</div></div>'
        "</div>"
    )
    res = em.extract_from_standard()
    assert em.layout_label == "standard-songs"
    assert _texts(res) == ["song A", "song B"]


def test_standard_sports_standings_extracts_tab_children():
    em = _make_extractor(
        '<div id="rso">'
        '<div id="kp-wp-tab-SportsStandings"><div>team 1</div><div>team 2</div></div>'
        "</div>"
    )
    res = em.extract_from_standard()
    assert em.layout_label == "standard-sports-standings"
    assert _texts(res) == ["team 1", "team 2"]


def test_standard_airfares_extracts_a6k0a_children():
    em = _make_extractor(
        '<div id="rso"><div id="kp-wp-tab-AIRFARES">'
        '<div class="A6K0A">fare 1</div><div class="A6K0A">fare 2</div>'
        "</div></div>"
    )
    res = em.extract_from_standard()
    assert em.layout_label == "standard-airfares"
    assert _texts(res) == ["fare 1", "fare 2"]


def test_standard_fallback_label_on_empty_rso():
    # No kp-wp-tab-* container matches and the generic extraction yields nothing,
    # so the label settles on the standard-fallback empty path.
    em = _make_extractor('<div id="rso"><div></div></div>')
    res = em.extract_from_standard()
    assert em.layout_label == "standard-fallback"
    assert _texts(res) == []


def test_extract_from_standard_sub_type_unknown_returns_empty():
    # A sub_type with no recipe in _STANDARD_LAYOUTS yields an empty result
    # rather than raising (the method default is still "").
    em = _make_extractor('<div id="rso"><div class="g">x</div></div>')
    assert em._extract_from_standard_sub_type("not-a-layout") == []
    assert em._extract_from_standard_sub_type() == []


# extract_from_top_bar: top-bars-divs / top-bars-children ----------------------


def test_top_bar_divs_when_rso_has_result_divs():
    body = (
        '<div id="rcnt"><div class="XqFnDf"><div>topbar content</div></div></div>'
        '<div id="rso"><div class="g">result one</div><div class="g">result two</div></div>'
    )
    em = _make_extractor(body, top_bars_css="div.XqFnDf, div.M8OgIe")
    res = em.extract_from_top_bar()
    assert em.layout_label == "top-bars-divs"
    assert _texts(res) == ["topbar content", "result one", "result two"]


def test_top_bar_children_when_rso_has_no_result_divs():
    body = (
        '<div id="rcnt"><div class="XqFnDf"><div>topbar content</div></div></div>'
        '<div id="rso"><div class="other">plain child</div></div>'
    )
    em = _make_extractor(body, top_bars_css="div.XqFnDf, div.M8OgIe")
    res = em.extract_from_top_bar()
    assert em.layout_label == "top-bars-children"
    assert _texts(res) == ["topbar content", "plain child"]


# extract_from_left_bar / extract_from_no_rso ----------------------------------


def test_left_bar_extracts_tzhb6b_document_wide():
    # NOTE pins current behavior: extraction is scoped to the whole document, not
    # to the left-bar div, so it also captures div.TzHB6b inside rso.
    em = _make_extractor(
        '<div class="OeVqAd">leftbar marker</div>'
        '<div id="rso"><div class="TzHB6b">tz in rso</div></div>'
        '<div class="TzHB6b">tz outside rso</div>'
    )
    res = em.extract_from_left_bar()
    assert _texts(res) == ["tz in rso", "tz outside rso"]


def test_no_rso_extracts_sec1_links():
    em = _make_extractor('<div class="UDZeY OTFaAf"><g-more-link>more1</g-more-link></div>')
    res = em.extract_from_no_rso()
    assert _texts(res) == ["more1"]


def test_no_rso_appends_sec2_once_per_page():
    # The trailing div.WvKfwe.a3spGf section is page-level, so its content must
    # appear once regardless of how many sec1 blocks precede it (it previously
    # re-appended once per sec1 div).
    em = _make_extractor(
        '<div class="UDZeY OTFaAf"><g-more-link>more1</g-more-link></div>'
        '<div class="UDZeY OTFaAf"><g-more-link>more2</g-more-link></div>'
        '<div class="WvKfwe a3spGf"><div>sec2 content</div></div>'
    )
    res = em.extract_from_no_rso()
    texts = _texts(res)
    assert texts.count("sec2 content") == 1
    assert [t for t in texts if t != "sec2 content"] == ["more1", "more2"]
