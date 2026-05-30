"""Tests for ExtractorMain component validity filtering"""

from WebSearcher import utils
from WebSearcher.extractors.extractor_main import ExtractorMain


def comp(html: str):
    """Build a single component ``Node`` from an HTML fragment."""
    return utils.make_soup(f'<div class="wrap">{html}</div>').css_first("div.wrap")


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
