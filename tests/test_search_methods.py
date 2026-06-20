"""Tests for the browser backends' send_request failure-path capture.

The backends are driven with fake page/driver/tab objects so no browser is
needed. Two behaviors are pinned: a navigation that lands somewhere (e.g. a
/sorry/ CAPTCHA redirect) but then times out on #search still captures the
live URL and HTML; a failure *before* navigation captures nothing, so the
previous query's page is never recorded under the new query.
"""

import logging

from WebSearcher.models.searches import SearchParams
from WebSearcher.searchers.patchright_searcher import PatchrightSearcher
from WebSearcher.searchers.selenium_searcher import SeleniumDriver
from WebSearcher.searchers.zendriver_searcher import ZendriverSearcher

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


# Selenium ----------------------------------------------------------------------


class FakeDriverNavFails:
    """get raises before navigating; the browser stays on the previous SERP."""

    current_url = PREV_URL
    page_source = "<html>previous serp</html>"

    def get(self, url):
        raise Exception("timeout: page load")

    def delete_all_cookies(self):
        return None


def test_selenium_nav_failure_no_stale_capture(monkeypatch):
    monkeypatch.setattr("WebSearcher.searchers.selenium_searcher.time.sleep", lambda s: None)
    searcher = SeleniumDriver.__new__(SeleniumDriver)
    searcher.log = LOG
    searcher.driver = FakeDriverNavFails()
    searcher.browser_info = {}
    params = SearchParams.create({"qry": "test"})
    out = searcher.send_request(params)
    assert out.url == params.url  # request URL kept, not the previous page's
    assert out.html == ""


# Zendriver ----------------------------------------------------------------------


class FakeCookies:
    def clear(self):
        return None


class FakeTabBlocked:
    url = SORRY_URL

    def select(self, selector, timeout=None):
        raise Exception("Timeout waiting for #search")

    def get_content(self):
        return SORRY_HTML


class FakeBrowserBlocked:
    cookies = FakeCookies()

    def get(self, url):
        return FakeTabBlocked()


class FakeTabPrev:
    url = PREV_URL


class FakeBrowserNavFails:
    cookies = FakeCookies()

    def get(self, url):
        raise Exception("CDP timeout")


def make_zendriver(browser, tab) -> ZendriverSearcher:
    searcher = ZendriverSearcher.__new__(ZendriverSearcher)
    searcher.log = LOG
    searcher.browser = browser
    searcher.tab = tab
    searcher.browser_info = {}
    searcher._run = lambda result: result  # fakes return values, not coroutines
    return searcher


def test_zendriver_block_capture(monkeypatch):
    monkeypatch.setattr("WebSearcher.searchers.zendriver_searcher.time.sleep", lambda s: None)
    tab = FakeTabPrev()  # pre-navigation tab; goto swaps in the blocked one
    out = make_zendriver(FakeBrowserBlocked(), tab).send_request(
        SearchParams.create({"qry": "test"})
    )
    assert out.url == SORRY_URL
    assert out.html == SORRY_HTML


def test_zendriver_nav_failure_no_stale_capture(monkeypatch):
    monkeypatch.setattr("WebSearcher.searchers.zendriver_searcher.time.sleep", lambda s: None)
    params = SearchParams.create({"qry": "test"})
    out = make_zendriver(FakeBrowserNavFails(), FakeTabPrev()).send_request(params)
    assert out.url == params.url
    assert out.html == ""
