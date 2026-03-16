"""Tests for SERP feature extraction"""

from WebSearcher.feature_extractor import FeatureExtractor


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


# No results notice ------------------------------------------------------------


def test_no_results_notice_detected():
    html = make_html("Your search - <b>asdfqwerty</b> - did not match any documents.")
    features = FeatureExtractor.extract_features(html)
    assert features.notice_no_results is True


def test_no_results_notice_absent():
    html = make_html("<div>Normal results here</div>")
    features = FeatureExtractor.extract_features(html)
    assert features.notice_no_results is False


# String match features --------------------------------------------------------


def test_shortened_query_notice():
    html = make_html("(and any subsequent words) was ignored because we limit queries to 32 words.")
    features = FeatureExtractor.extract_features(html)
    assert features.notice_shortened_query is True


def test_server_error_notice():
    html = make_html(
        "We're sorry but it appears that there has been an internal server error "
        "while processing your request."
    )
    features = FeatureExtractor.extract_features(html)
    assert features.notice_server_error is True


def test_infinity_scroll():
    html = make_html('<span class="RVQdVd">More results</span>')
    features = FeatureExtractor.extract_features(html)
    assert features.infinity_scroll is True


def test_no_string_matches():
    html = make_html("<div>clean page</div>")
    features = FeatureExtractor.extract_features(html)
    assert features.notice_shortened_query is False
    assert features.notice_server_error is False
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
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        make_html('<div id="result-stats">About 99 results (0.3 seconds)</div>'), "lxml"
    )
    features = FeatureExtractor.extract_features(soup)
    assert features.result_estimate_count == 99
    assert features.result_estimate_time == 0.3


# model_dump -------------------------------------------------------------------


def test_features_model_dump():
    html = make_html('<div id="result-stats">About 10 results (0.1 seconds)</div>')
    features = FeatureExtractor.extract_features(html)
    d = features.model_dump()
    assert isinstance(d, dict)
    assert d["result_estimate_count"] == 10
    assert d["captcha"] is False
