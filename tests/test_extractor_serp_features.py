"""Tests for SERP feature extraction"""

from pathlib import Path

from WebSearcher.extractors.extractor_serp_features import FeatureExtractor


def make_html(body="", lang="en"):
    return f'<html lang="{lang}"><body>{body}</body></html>'


# Result estimate extraction ---------------------------------------------------


def test_extract_result_count_and_time():
    html = make_html('<div id="result-stats">About 1,234,567 results (0.42 seconds)</div>')
    features = FeatureExtractor.extract_features(html)
    assert features.result_estimate_count == 1234567
    assert features.result_estimate_time == 0.42


def test_extract_result_count_no_comma():
    html = make_html('<div id="result-stats">About 500 results (0.1 seconds)</div>')
    features = FeatureExtractor.extract_features(html)
    assert features.result_estimate_count == 500


def test_extract_result_count_short_time():
    html = make_html('<div id="result-stats">About 100 results (0.05s)</div>')
    features = FeatureExtractor.extract_features(html)
    assert features.result_estimate_count == 100
    assert features.result_estimate_time == 0.05


def test_extract_no_result_stats():
    html = make_html("<div>some content</div>")
    features = FeatureExtractor.extract_features(html)
    assert features.result_estimate_count is None
    assert features.result_estimate_time is None


# Language extraction ----------------------------------------------------------


def test_extract_language():
    html = make_html("<p>hello</p>", lang="en")
    features = FeatureExtractor.extract_features(html)
    assert features.language == "en"


def test_extract_language_other():
    html = make_html("<p>hola</p>", lang="es")
    features = FeatureExtractor.extract_features(html)
    assert features.language == "es"


def test_extract_no_language():
    html = "<html><body>no lang attr</body></html>"
    features = FeatureExtractor.extract_features(html)
    assert features.language is None


# String match features --------------------------------------------------------
# Note: no-results and query-truncation notices are `notice` components now
# (see tests/test_notices.py), not feature flags.


def test_server_error_flag():
    html = make_html(
        "We're sorry but it appears that there has been an internal server error "
        "while processing your request."
    )
    features = FeatureExtractor.extract_features(html)
    assert features.server_error is True


def test_infinity_scroll():
    html = make_html('<span class="RVQdVd">More results</span>')
    features = FeatureExtractor.extract_features(html)
    assert features.infinity_scroll is True


def test_no_string_matches():
    html = make_html("<div>clean page</div>")
    features = FeatureExtractor.extract_features(html)
    assert features.server_error is False
    assert features.infinity_scroll is False


# CAPTCHA detection ------------------------------------------------------------


def test_captcha_detected():
    html = make_html("<div>Please solve the CAPTCHA to continue</div>")
    features = FeatureExtractor.extract_features(html)
    assert features.captcha is True


def test_captcha_absent():
    html = make_html("<div>Normal page</div>")
    features = FeatureExtractor.extract_features(html)
    assert features.captcha is False


SORRY_URL = "https://www.google.com/sorry/index?continue=https://www.google.com/search%3Fq%3Dtest&q=REDACTED_TOKEN"


def test_captcha_from_sorry_redirect_url():
    # The redirect URL alone flags a CAPTCHA -- the wait timeout can leave the
    # captured HTML empty, so the text marker is not always present.
    features = FeatureExtractor.extract_features("", url=SORRY_URL)
    assert features.captcha is True


def test_captcha_clean_html_normal_url():
    html = make_html("<div>Normal page</div>")
    features = FeatureExtractor.extract_features(html, url="https://www.google.com/search?q=test")
    assert features.captcha is False


def test_captcha_sorry_fixture_html():
    # No url passed: the fixture's page text alone must trip the HTML path.
    fp = Path(__file__).parent / "fixtures" / "sorry_index.html"
    features = FeatureExtractor.extract_features(fp.read_text())
    assert features.captcha is True


# Location overlay -------------------------------------------------------------


def test_location_overlay_detected():
    html = make_html('<div id="lb">Use precise location</div>')
    features = FeatureExtractor.extract_features(html)
    assert features.overlay_precise_location is True


def test_location_overlay_absent():
    html = make_html('<div id="lb">Something else</div>')
    features = FeatureExtractor.extract_features(html)
    assert features.overlay_precise_location is False


def test_location_overlay_no_div():
    html = make_html("<div>no lb div</div>")
    features = FeatureExtractor.extract_features(html)
    assert features.overlay_precise_location is False


# BeautifulSoup input ----------------------------------------------------------


def test_extract_from_soup():
    soup = make_soup('<div id="result-stats">About 99 results (0.3 seconds)</div>')
    features = FeatureExtractor.extract_features(soup)
    assert features.result_estimate_count == 99
    assert features.result_estimate_time == 0.3


# BeautifulSoup input -- soup-path parity (no str(soup)) -----------------------


def make_soup(body="", lang="en"):
    from WebSearcher import utils

    return utils.make_soup(make_html(body, lang))


def test_soup_language():
    features = FeatureExtractor.extract_features(make_soup("<p>hola</p>", lang="es"))
    assert features.language == "es"


def test_soup_server_error_flag():
    features = FeatureExtractor.extract_features(
        make_soup(
            "We're sorry but it appears that there has been an internal server error "
            "while processing your request."
        )
    )
    assert features.server_error is True


def test_soup_infinity_scroll():
    features = FeatureExtractor.extract_features(
        make_soup('<span class="RVQdVd">More results</span>')
    )
    assert features.infinity_scroll is True


def test_soup_infinity_scroll_extra_attrs_not_matched():
    # Exact-substring parity with the old str(soup) check: extra attributes on the
    # span break the literal match, so infinity_scroll stays False.
    features = FeatureExtractor.extract_features(
        make_soup('<span class="RVQdVd" data-x="y">More results</span>')
    )
    assert features.infinity_scroll is False


def test_soup_clean_page_no_features():
    features = FeatureExtractor.extract_features(make_soup("<div>clean page</div>"))
    assert features.server_error is False
    assert features.infinity_scroll is False
    assert features.overlay_precise_location is False
    assert features.captcha is False


# model_dump -------------------------------------------------------------------


def test_features_model_dump():
    html = make_html('<div id="result-stats">About 10 results (0.1 seconds)</div>')
    features = FeatureExtractor.extract_features(html)
    d = features.model_dump()
    assert isinstance(d, dict)
    assert d["result_estimate_count"] == 10
    assert d["captcha"] is False
