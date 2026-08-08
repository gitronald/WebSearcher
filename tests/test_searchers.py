"""Tests for SearchEngine record building and saving (to_record / save_record)"""

import logging

import orjson

from WebSearcher.models.data import ParsedSERP
from WebSearcher.searchers import SearchEngine

# Minimal SERP/parsed fixtures ------------------------------------------------

SERP = {
    "qry": "pizza",
    "loc": "Boston,Massachusetts,United States",
    "lang": "en",
    "url": "https://www.google.com/search?q=pizza",
    "html": "<html>raw serp</html>",
    "timestamp": "2026-06-05T12:00:00",
    "response_code": 200,
    "user_agent": "test-agent",
    "serp_id": "abc123",
    "crawl_id": "crawl-1",
    "version": "0.9.0",
    "method": "requests",
}

PARSED = ParsedSERP(
    crawl_id="crawl-1",
    serp_id="abc123",
    version="0.9.0",
    method="requests",
    features={"has_ai_overview": False},
    results=[{"sub_rank": 0, "type": "general", "title": "t", "url": "https://x.com"}],
)


def make_engine(serp: dict, parsed: ParsedSERP) -> SearchEngine:
    """Construct a SearchEngine without starting a driver (bypass __init__)."""
    se = SearchEngine.__new__(SearchEngine)
    se.serp = serp
    se.parsed = parsed
    se.log = logging.getLogger("test_searchers")
    return se


# to_record -------------------------------------------------------------------


def test_to_record_excludes_html():
    record = make_engine(SERP, PARSED).to_record()
    assert "html" not in record


def test_to_record_keys_are_metadata_plus_features_results():
    record = make_engine(SERP, PARSED).to_record()
    expected = {k for k in SERP if k != "html"} | {"features", "results"}
    assert set(record) == expected


def test_to_record_does_not_duplicate_identity_from_parsed():
    # serp identity wins; parsed's own crawl_id/serp_id/version/method never enter
    record = make_engine(SERP, PARSED).to_record()
    assert record["serp_id"] == "abc123"
    assert record["crawl_id"] == "crawl-1"
    assert record["features"] == PARSED.features
    assert record["results"] == PARSED.results


# save_record -----------------------------------------------------------------


def test_save_record_writes_one_json_line(tmp_path):
    fp = tmp_path / "parsed.json"
    se = make_engine(SERP, PARSED)
    se.save_record(append_to=fp)
    lines = fp.read_text().splitlines()
    assert len(lines) == 1
    assert orjson.loads(lines[0]) == se.to_record()


def test_save_record_stamps_ws_version(tmp_path):
    fp = tmp_path / "parsed.json"
    make_engine(SERP, PARSED).save_record(append_to=fp, ws_version="0.9.0")
    loaded = orjson.loads(fp.read_text().splitlines()[0])
    assert loaded["ws_version"] == "0.9.0"


def test_save_record_omits_ws_version_when_unset(tmp_path):
    fp = tmp_path / "parsed.json"
    make_engine(SERP, PARSED).save_record(append_to=fp)
    loaded = orjson.loads(fp.read_text().splitlines()[0])
    assert "ws_version" not in loaded


def test_save_record_requires_append_to(tmp_path):
    # No path -> warn and no-op (no file written), unlike a raising error
    se = make_engine(SERP, PARSED)
    se.save_record(append_to="")
    assert list(tmp_path.iterdir()) == []


def test_parse_serp_resets_stale_parse_on_error():
    # A parse failure must not leave the previous query's parse (and its
    # captcha feature) attributed to the current one.
    se = make_engine({**SERP, "html": None}, PARSED)  # None html -> parse raises
    se.parse_serp()
    assert se.parsed.features == {}
    assert se.parsed.results == []


def test_parse_serp_threads_serp_url():
    # The stored response URL feeds the captcha feature (sorry-redirect signal).
    sorry_serp = {
        **SERP,
        "html": "<html><body>blocked</body></html>",
        "url": "https://www.google.com/sorry/index?continue=x",
    }
    se = make_engine(sorry_serp, ParsedSERP())
    se.parse_serp()
    assert se.parsed.features["captcha"] is True


def test_save_record_writes_metadata_only_line_when_unparsed(tmp_path):
    # Error/unparsed path: empty ParsedSERP still yields a metadata row
    # (save_parsed would skip it; save_record must not, for row uniformity).
    fp = tmp_path / "parsed.json"
    se = make_engine(SERP, ParsedSERP())
    se.save_record(append_to=fp)
    loaded = orjson.loads(fp.read_text().splitlines()[0])
    assert loaded["serp_id"] == "abc123"
    assert loaded["features"] == {}
    assert loaded["results"] == []


# SerpBase searcher -----------------------------------------------------------


def test_serpbase_searcher_no_key_graceful():
    # Missing API key -> empty ResponseOutput (response_code 0), no exception,
    # so a crawl without SERPBASE_API_KEY leaves the other methods unaffected.
    from WebSearcher.models.configs import SerpBaseConfig
    from WebSearcher.models.searches import SearchParams
    from WebSearcher.searchers.serpbase_searcher import SerpBaseSearcher

    searcher = SerpBaseSearcher(
        config=SerpBaseConfig(api_key=""), logger=logging.getLogger("test_searchers")
    )
    out = searcher.send_request(SearchParams(qry="pizza"))
    assert out.response_code == 0
    assert out.html == ""


def test_serpbase_searcher_renders_parseable_serp(monkeypatch):
    # With a key (here via env var) the JSON response renders into minimal
    # Google-style HTML that the standard parser turns into `general` results.
    from WebSearcher.models.configs import SerpBaseConfig
    from WebSearcher.models.searches import SearchParams
    from WebSearcher.parsers.parse_serp import parse_serp
    from WebSearcher.searchers.serpbase_searcher import SerpBaseSearcher

    monkeypatch.setenv("SERPBASE_API_KEY", "test-key")

    class FakeResponse:
        status_code = 200
        url = "https://api.serpbase.dev/google/search?q=pizza&api_key=test-key"

        def json(self):
            return {
                "organic_results": [
                    {
                        "title": "Best Pizza in Town",
                        "link": "https://example.com/pizza",
                        "snippet": "A tiny pizzeria serving wood-fired margherita since 1987.",
                    },
                    {
                        "title": "Pizza Wiki",
                        "link": "https://example.org/wiki/pizza",
                        "snippet": "Pizza is a traditional Italian dish consisting of a flat base.",
                    },
                ]
            }

    class FakeSession:
        headers = {}

        def get(self, url, params=None, timeout=None):
            assert params["q"] == "pizza"
            assert params["api_key"] == "test-key"
            return FakeResponse()

        def close(self):
            pass

    searcher = SerpBaseSearcher(
        config=SerpBaseConfig(api_key=""), logger=logging.getLogger("test_searchers")
    )
    searcher.sesh = FakeSession()
    out = searcher.send_request(SearchParams(qry="pizza"))
    assert out.response_code == 200
    assert '<div id="rso">' in out.html
    assert '<div class="g">' in out.html

    parsed = parse_serp(out.html, url=out.url)
    general = [r for r in parsed["results"] if r["type"] == "general"]
    assert len(general) == 2
    assert general[0]["title"] == "Best Pizza in Town"
    assert general[0]["url"] == "https://example.com/pizza"
    assert "wood-fired margherita" in general[0]["text"]
