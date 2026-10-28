"""Tests for the patchright backend's capture steps (plan 066), on fake pages.

Pinned: each request starts from a blank page (replacing the page when a late
navigation of the previous SERP interrupts the reset); the capture settles the
page and retries ``content()`` only while the page is navigating; a capture
without ``#search`` is flagged; and the AI-overview expansion logs its outcome.
"""

import logging
from typing import override

import pytest

from WebSearcher.models.configs import PatchrightConfig
from WebSearcher.models.data import ResponseOutput
from WebSearcher.models.searches import SearchParams
from WebSearcher.searchers import patchright_searcher
from WebSearcher.searchers.patchright_searcher import (
    CONTENT_ATTEMPTS,
    SHOW_MORE_EXPANDED_SELECTOR,
    SHOW_MORE_SELECTOR,
    PatchrightSearcher,
)

LOG = logging.getLogger("test_patchright_capture")
PREV_URL = "https://www.google.com/search?q=previous+query"
SERP_HTML = '<html><body><div id="search"><div id="rso">results</div></div></body></html>'
SHELL_HTML = (
    "<html><body><noscript>Please click here if you are not redirected</noscript></body></html>"
)
NAVIGATING = "Page.content: Unable to retrieve content because the page is navigating and changing the content."


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(patchright_searcher.time, "sleep", lambda s: None)


class FakeResponse:
    status = 200


class FakePage:
    """A page that navigates as asked and serves ``contents`` in turn.

    Each item of ``contents`` is the HTML to return, or an exception to raise.
    ``calls`` records every method call, in order.
    """

    def __init__(self, url="about:blank", contents=(SERP_HTML,)):
        self.url = url
        self.contents = list(contents)
        self.calls: list[tuple] = []
        self.closed = False

    def goto(self, url, wait_until=None, timeout=None):
        self.calls.append(("goto", url))
        self.url = url
        return FakeResponse()

    def wait_for_selector(self, selector, state=None, timeout=None):
        self.calls.append(("wait_for_selector", selector, state))

    def wait_for_load_state(self, state, timeout=None):
        self.calls.append(("wait_for_load_state", state))

    def content(self):
        self.calls.append(("content",))
        item = self.contents.pop(0) if len(self.contents) > 1 else self.contents[0]
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        self.closed = True


class FakeLateNavPage(FakePage):
    """Holds the previous SERP, whose late navigation interrupts the blank-page reset."""

    @override
    def goto(self, url, wait_until=None, timeout=None):
        self.calls.append(("goto", url))
        raise Exception(
            f'Navigation to "{url}" is interrupted by another navigation to "{PREV_URL}"'
        )


class FakeContext:
    def __init__(self, new_page):
        self._new_page = new_page
        self.cleared = 0

    def new_page(self):
        return self._new_page

    def clear_cookies(self):
        self.cleared += 1


def make_patchright(page, new_page=None) -> PatchrightSearcher:
    searcher = PatchrightSearcher(PatchrightConfig(), LOG)
    searcher.page = page
    searcher.context = FakeContext(new_page or FakePage())
    return searcher


def search(searcher: PatchrightSearcher, **params) -> ResponseOutput:
    return searcher.send_request(SearchParams.create({"qry": "test", **params}))


# Reset to a blank page ---------------------------------------------------------


def test_reset_navigates_to_blank_before_search():
    page = FakePage(url=PREV_URL)
    params = SearchParams.create({"qry": "test"})
    out = make_patchright(page).send_request(params)
    gotos = [c[1] for c in page.calls if c[0] == "goto"]
    assert gotos == ["about:blank", params.url]
    assert out.html == SERP_HTML


def test_reset_skipped_on_blank_page():
    page = FakePage()
    params = SearchParams.create({"qry": "test"})
    make_patchright(page).send_request(params)
    assert [c[1] for c in page.calls if c[0] == "goto"] == [params.url]


def test_late_navigation_replaces_page_and_never_records_previous_serp():
    old = FakeLateNavPage(url=PREV_URL, contents=["<html>previous query's SERP</html>"])
    new = FakePage()
    searcher = make_patchright(old, new_page=new)
    params = SearchParams.create({"qry": "test"})
    out = searcher.send_request(params)
    assert old.closed
    assert searcher.page is new
    assert out.url == params.url
    assert out.html == SERP_HTML


# Settle and capture ------------------------------------------------------------


def test_capture_settles_then_checks_search_attached():
    page = FakePage()
    search(make_patchright(page))
    after_goto = [c for c in page.calls if c[0] != "goto"]
    assert after_goto == [
        ("wait_for_selector", "#search", None),
        ("wait_for_load_state", "load"),
        ("wait_for_load_state", "networkidle"),
        ("wait_for_selector", "#search", "attached"),
        ("content",),
    ]


def test_content_retried_while_page_is_navigating():
    page = FakePage(contents=[Exception(NAVIGATING), SERP_HTML])
    out = search(make_patchright(page))
    assert out.html == SERP_HTML
    assert out.has_search is True
    assert [c for c in page.calls if c[0] == "content"] == [("content",)] * 2
    # The retry settles the page and re-checks #search before reading it again
    assert page.calls[-2] == ("wait_for_selector", "#search", "attached")


def test_content_retry_gives_up_after_attempts(caplog):
    page = FakePage(contents=[Exception(NAVIGATING)])
    with caplog.at_level(logging.DEBUG, logger=LOG.name):
        out = search(make_patchright(page))
    # The main capture and the failure path's capture each try CONTENT_ATTEMPTS times
    assert len([c for c in page.calls if c[0] == "content"]) == 2 * CONTENT_ATTEMPTS
    assert out.html == ""
    assert [r for r in caplog.records if r.levelno == logging.ERROR]


def test_other_content_errors_not_retried():
    page = FakePage(contents=[Exception("Target closed")])
    search(make_patchright(page))
    # One try in the main capture, one in the failure path
    assert len([c for c in page.calls if c[0] == "content"]) == 2


def test_capture_without_search_is_flagged(caplog):
    page = FakePage(contents=[SHELL_HTML])
    with caplog.at_level(logging.DEBUG, logger=LOG.name):
        out = search(make_patchright(page))
    assert out.html == SHELL_HTML
    assert out.has_search is False
    assert [
        r
        for r in caplog.records
        if getattr(r, "event", None) == "capture" and r.levelno == logging.WARNING
    ]


def test_has_search_in_response_dump():
    assert ResponseOutput(html=SERP_HTML).model_dump()["has_search"] is True
    assert ResponseOutput(html="").model_dump()["has_search"] is False


# AI-overview expansion -----------------------------------------------------------


class FakeLocator:
    def __init__(self, count=1, aria_expanded=None, click_error=None):
        self._count = count
        self.aria_expanded = aria_expanded
        self.click_error = click_error

    @property
    def first(self):
        return self

    def count(self):
        return self._count

    def get_attribute(self, name, timeout=None):
        return self.aria_expanded

    def click(self, timeout=None):
        if self.click_error:
            raise self.click_error
        if self.aria_expanded == "false":
            self.aria_expanded = "true"


class FakeExpandPage(FakePage):
    def __init__(self, show_more: FakeLocator, expands=True):
        super().__init__(contents=["<html>expanded</html>"])
        self.show_more = show_more
        self.expands = expands

    def locator(self, selector):
        if selector == SHOW_MORE_SELECTOR:
            return self.show_more
        return FakeLocator(click_error=Exception("no show-all control"))

    @override
    def wait_for_selector(self, selector, state=None, timeout=None):
        super().wait_for_selector(selector, state, timeout)
        if selector == SHOW_MORE_EXPANDED_SELECTOR and not self.expands:
            raise Exception("Timeout waiting for aria-expanded")


@pytest.mark.parametrize(
    ("show_more", "expands", "outcome", "html"),
    [
        (FakeLocator(aria_expanded="false"), True, "expanded", "<html>expanded</html>"),
        (FakeLocator(aria_expanded="false"), False, "not_expanded", None),
        (FakeLocator(aria_expanded=None), True, "unconfirmed", "<html>expanded</html>"),
        (FakeLocator(count=0), True, "no_control", None),
        (FakeLocator(click_error=Exception("Timeout 5000ms")), True, "click_failed", None),
    ],
)
def test_expand_ai_overview_outcomes(caplog, show_more, expands, outcome, html):
    searcher = make_patchright(FakeExpandPage(show_more, expands=expands))
    with caplog.at_level(logging.DEBUG, logger=LOG.name):
        assert searcher.expand_ai_overview() == html
    messages = [r.getMessage() for r in caplog.records if getattr(r, "event", None) == "ai_expand"]
    assert messages == [f"SERP | ai_expand | {outcome}"]
