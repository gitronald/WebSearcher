"""Searcher, config, and IO regressions from the whole-package review."""

import logging

import pytest
import requests

from WebSearcher import utils
from WebSearcher.locations import get_latest_url, write_csv
from WebSearcher.models.configs import PatchrightConfig, RequestsConfig
from WebSearcher.models.searches import SearchParams
from WebSearcher.searchers.patchright_searcher import PatchrightSearcher
from WebSearcher.searchers.requests_searcher import RequestsSearcher

LOG = logging.getLogger("test")


class _Response:
    def __init__(self, url: str, content: bytes = b"<html>ok</html>", status: int = 200):
        self.url = url
        self.content = content
        self.status_code = status
        self.text = content.decode()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class _Session(requests.Session):
    """Records the headers each request was sent with, without touching the network."""

    def __init__(self):
        super().__init__()
        self.sent: list[dict] = []

    def get(self, url, **kwargs):  # type: ignore[override]
        merged = {**self.headers, **(kwargs.get("headers") or {})}
        self.sent.append(merged)
        return _Response(url)


def _searcher(sesh: requests.Session | None = None) -> RequestsSearcher:
    cfg = RequestsConfig(sesh=sesh, unzip=False)
    return RequestsSearcher(config=cfg, logger=LOG)


def test_requests_config_honors_supplied_session():
    sesh = _Session()
    searcher = _searcher(sesh)
    assert searcher.sesh is sesh
    assert _searcher().sesh is not sesh  # built from the headers when unset


def test_per_search_headers_do_not_leak_into_the_session():
    sesh = _Session()
    searcher = _searcher(sesh)
    first = searcher.send_request(SearchParams(qry="a", headers={"User-Agent": "X"}))
    second = searcher.send_request(SearchParams(qry="b"))
    # A caller-supplied session keeps its own headers; only the first request
    # carries the per-search override, and the recorded user_agent follows suit.
    assert sesh.sent[0]["User-Agent"] == "X"
    assert sesh.sent[1]["User-Agent"] == sesh.headers["User-Agent"]
    assert first.user_agent == "X"
    assert second.user_agent == sesh.headers["User-Agent"]
    assert "X" not in sesh.headers.values()


def test_recorded_user_agent_matches_lowercase_header_override():
    sesh = requests.Session()
    sent: list[str] = []

    def _get(url, **kwargs):
        prepared = sesh.prepare_request(requests.Request("GET", url, headers=kwargs["headers"]))
        sent.append(prepared.headers["User-Agent"])
        return _Response(url)

    sesh.get = _get  # type: ignore[method-assign]
    out = _searcher(sesh).send_request(SearchParams(qry="a", headers={"user-agent": "X"}))
    assert sent == ["X"]
    assert out.user_agent == "X"


def test_patchright_cleanup_stops_driver_when_context_close_fails():
    class _Context:
        def close(self):
            raise RuntimeError("browser gone")

    class _Playwright:
        stopped = False

        def stop(self):
            self.stopped = True

    searcher = PatchrightSearcher.__new__(PatchrightSearcher)
    searcher.log = LOG
    searcher.playwright = _Playwright()
    searcher.context = _Context()
    searcher.page = None
    searcher._tmp_profile = ""
    searcher._exit_hook = None
    pw = searcher.playwright
    assert searcher.cleanup() is False
    assert pw.stopped is True
    assert searcher.playwright is None


def _fake_patchright(monkeypatch, start=None, evaluate=None):
    """Stub ``sync_playwright`` and return the event list the stubs append to."""
    events: list[str] = []

    class _Page:
        def evaluate(self, expr):
            if evaluate is not None:
                raise evaluate
            return "UA"

    class _Context:
        browser = None
        pages = [_Page()]

        def close(self):
            events.append("context.close")

    class _Chromium:
        def launch_persistent_context(self, **kw):
            return _Context()

    class _Playwright:
        chromium = _Chromium()

        def stop(self):
            events.append("playwright.stop")

    class _Starter:
        def start(self):
            if start is not None:
                raise start
            return _Playwright()

    import patchright.sync_api

    monkeypatch.setattr(patchright.sync_api, "sync_playwright", _Starter)
    return events


def test_patchright_failed_driver_start_removes_temp_profile(monkeypatch, tmp_path):
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    _fake_patchright(monkeypatch, start=RuntimeError("no driver"))
    searcher = PatchrightSearcher(PatchrightConfig(), LOG)
    with pytest.raises(RuntimeError, match="no driver"):
        searcher.init_driver()
    assert list(tmp_path.iterdir()) == []
    assert searcher._tmp_profile == ""
    assert searcher._exit_hook is None


def test_patchright_failure_after_launch_closes_browser_and_driver(monkeypatch, tmp_path):
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    events = _fake_patchright(monkeypatch, evaluate=RuntimeError("page crashed"))
    searcher = PatchrightSearcher(PatchrightConfig(), LOG)
    with pytest.raises(RuntimeError, match="page crashed"):
        searcher.init_driver()
    assert events == ["context.close", "playwright.stop"]
    assert list(tmp_path.iterdir()) == []
    assert searcher.playwright is None
    assert searcher._exit_hook is None


# utils IO -----------------------------------------------------------------------


def test_write_lines_creates_parent_dir_and_round_trips_unicode(tmp_path):
    fp = tmp_path / "nested" / "out.json"
    utils.write_lines([{"q": "café — 日本"}], fp)
    assert utils.read_lines(fp) == [{"q": "café — 日本"}]
    html = tmp_path / "page.html"
    html.write_text("<p>naïve</p>", encoding="utf-8")
    assert utils.load_html(html) == "<p>naïve</p>"


def test_utc_timestamp_is_naive_iso():
    ts = utils.utc_timestamp()
    assert "T" in ts and "+" not in ts and not ts.endswith("Z")


# locations ----------------------------------------------------------------------


def test_get_latest_url_raises_clearly_when_no_link(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda url, timeout: _Response(url, b"<html><a href='/x'>x</a></html>")
    )
    with pytest.raises(ValueError, match="no geotargets link"):
        get_latest_url("https://example.invalid/page")


def test_get_latest_url_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, timeout: _Response(url, b"", status=503))
    with pytest.raises(requests.HTTPError):
        get_latest_url("https://example.invalid/page")


def test_get_latest_url_picks_latest(monkeypatch):
    page = b"<a href='/adwords/api/docs/geotargets-2024-01-01.csv'>a</a><a href='/adwords/api/docs/geotargets-2025-01-01.csv'>b</a>"
    monkeypatch.setattr(requests, "get", lambda url, timeout: _Response(url, page))
    assert get_latest_url("https://example.invalid/page").endswith("geotargets-2025-01-01.csv")


def test_write_csv_uses_newline_safe_terminator(tmp_path):
    fp = tmp_path / "geo.csv"
    write_csv(str(fp), lines=[["a", "b"], ["1", "2"]])
    raw = fp.read_bytes()
    assert raw == b"a,b\r\n1,2\r\n"
