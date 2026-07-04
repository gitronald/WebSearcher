"""Tests for the patchright backend's send_request failure-path capture.

The backend is driven with fake page objects so no browser is needed. Two
behaviors are pinned: a navigation that lands somewhere (e.g. a /sorry/ CAPTCHA
redirect) but then times out on #search still captures the live URL and HTML; a
failure *before* navigation captures nothing, so the previous query's page is
never recorded under the new query.
"""

import logging

from WebSearcher.models.searches import SearchParams
from WebSearcher.searchers.patchright_searcher import PatchrightSearcher

SORRY_URL = "https://www.google.com/sorry/index?continue=https://www.google.com/search%3Fq%3Dtest&q=REDACTED_TOKEN"
SORRY_HTML = "<html><body>solve the CAPTCHA</body></html>"
PREV_URL = "https://www.google.com/search?q=previous+query"

LOG = logging.getLogger("test_search_methods")


# Patchright -------------------------------------------------------------------


class FakeResponse:
    status = 429


class FakePageBlocked:
    """goto lands on the /sorry/ redirect; #search wait then times out."""

    def __init__(self):
        self.url = "about:blank"

    def goto(self, url, wait_until=None):
        self.url = SORRY_URL
        return FakeResponse()

    def wait_for_selector(self, selector, timeout=None):
        raise Exception("Timeout waiting for #search")

    def content(self):
        return SORRY_HTML


class FakePageNavFails:
    """goto raises before navigating; the page stays on the previous SERP."""

    url = PREV_URL

    def goto(self, url, wait_until=None):
        raise Exception("net::ERR_CONNECTION_RESET")


def make_patchright(page) -> PatchrightSearcher:
    searcher = PatchrightSearcher.__new__(PatchrightSearcher)
    searcher.log = LOG
    searcher.page = page
    searcher.context = None
    searcher.browser_info = {}
    return searcher


def test_patchright_block_capture(monkeypatch):
    monkeypatch.setattr("WebSearcher.searchers.patchright_searcher.time.sleep", lambda s: None)
    out = make_patchright(FakePageBlocked()).send_request(SearchParams.create({"qry": "test"}))
    assert out.url == SORRY_URL
    assert out.html == SORRY_HTML
    assert out.response_code == 429


def test_patchright_nav_failure_no_stale_capture(monkeypatch):
    monkeypatch.setattr("WebSearcher.searchers.patchright_searcher.time.sleep", lambda s: None)
    params = SearchParams.create({"qry": "test"})
    out = make_patchright(FakePageNavFails()).send_request(params)
    assert out.url == params.url  # request URL kept, not the previous page's
    assert out.html == ""
