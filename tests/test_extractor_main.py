"""Tests for ExtractorMain component validity filtering"""

from WebSearcher import utils
from WebSearcher.extractors.extractor_main import ExtractorMain


def comp(html: str):
    """Build a single component Tag from an HTML fragment."""
    return utils.make_soup(f'<div class="wrap">{html}</div>').find("div", {"class": "wrap"})


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


# is_valid: hidden-survey filter (now-live branch) -----------------------------
# This branch was dead before the `"attrs" in c` -> `hasattr(c, "attrs")` fix
# (the old guard tested child membership, not attribute presence). These tests
# pin the intended behavior: a ULSxyf container wrapping a promo-throttler is
# dropped, and both conditions are required.


def test_is_valid_drops_hidden_survey():
    # The component itself must carry class="ULSxyf" for the filter to fire.
    ulsxyf = utils.make_soup(
        '<div class="ULSxyf">Take our survey<promo-throttler></promo-throttler></div>'
    ).find("div", {"class": "ULSxyf"})
    assert ExtractorMain.is_valid(ulsxyf) is False


def test_is_valid_keeps_ulsxyf_without_throttler():
    ulsxyf = utils.make_soup('<div class="ULSxyf">A knowledge block, not a survey</div>').find(
        "div", {"class": "ULSxyf"}
    )
    assert ExtractorMain.is_valid(ulsxyf) is True


def test_is_valid_keeps_throttler_without_ulsxyf():
    other = utils.make_soup(
        '<div class="other">content<promo-throttler></promo-throttler></div>'
    ).find("div", {"class": "other"})
    assert ExtractorMain.is_valid(other) is True
