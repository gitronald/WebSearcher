"""Tests for the patchright backend's capture steps (plan 066), on fake pages.

Pinned: each request starts from a blank page (replacing the page when a late
navigation of the previous SERP interrupts the reset); the capture settles the
page (load, then a quiet network that ignores speculative prefetches) and
retries ``content()`` only while the page is navigating; a capture without
``#search`` is flagged; and the AI-overview expansion logs its outcome.
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
    IDLE_MS,
    NETWORKIDLE_TIMEOUT_MS,
    SHOW_MORE_EXPANDED_SELECTOR,
    SHOW_MORE_SELECTOR,
    NetworkTracker,
    PatchrightSearcher,
)

LOG = logging.getLogger("test_patchright_capture")
PREV_URL = "https://www.google.com/search?q=previous+query"
SERP_HTML = '<html><body><div id="search"><div id="rso">results</div></div></body></html>'
SHELL_HTML = (
    "<html><body><noscript>Please click here if you are not redirected</noscript></body></html>"
)
NAVIGATING = "Page.content: Unable to retrieve content because the page is navigating and changing the content."


class FakeClock:
    """Stands in for ``time.monotonic``; ``FakePage.wait_for_timeout`` advances it."""

    now = 0.0


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(patchright_searcher.time, "sleep", lambda s: None)
    FakeClock.now = 0.0
    monkeypatch.setattr(patchright_searcher.time, "monotonic", lambda: FakeClock.now)


class FakeRequest:
    def __init__(self, url, prefetch=False):
        self.url = url
        self.headers = {"sec-purpose": "prefetch"} if prefetch else {}


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
        self.handlers: dict[str, list] = {}

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def remove_listener(self, event, handler):
        self.handlers[event].remove(handler)

    def emit(self, event, request):
        for handler in list(self.handlers.get(event, [])):
            handler(request)

    def wait_for_timeout(self, ms):
        FakeClock.now += ms / 1000

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
        ("wait_for_selector", "#search", "attached"),
        ("content",),
    ]


class FakeBusyPage(FakePage):
    """A request is in flight from navigation until ``busy_s`` seconds pass."""

    def __init__(self, busy_s, **kwargs):
        super().__init__(**kwargs)
        self.busy_s = busy_s
        self.request: FakeRequest | None = FakeRequest("https://www.google.com/async/folsrch")
        self.captured_at: float | None = None

    @override
    def goto(self, url, wait_until=None, timeout=None):
        response = super().goto(url, wait_until, timeout)
        if url != "about:blank":
            self.emit("request", self.request)
        return response

    @override
    def wait_for_timeout(self, ms):
        super().wait_for_timeout(ms)
        if self.request is not None and FakeClock.now >= self.busy_s:
            self.emit("requestfinished", self.request)
            self.request = None

    @override
    def content(self):
        self.captured_at = FakeClock.now
        return super().content()


def test_capture_waits_for_request_in_flight():
    page = FakeBusyPage(busy_s=3.0)
    out = search(make_patchright(page))
    assert out.html == SERP_HTML
    assert page.captured_at is not None
    assert page.captured_at >= 3.0 + IDLE_MS / 1000


def test_capture_waits_no_longer_than_cap(caplog):
    page = FakeBusyPage(busy_s=60.0)
    with caplog.at_level(logging.DEBUG, logger=LOG.name):
        out = search(make_patchright(page))
    assert out.html == SERP_HTML
    assert page.captured_at is not None
    assert page.captured_at <= NETWORKIDLE_TIMEOUT_MS / 1000 + 0.2
    assert any("network busy at cap" in r.getMessage() for r in caplog.records)


def test_send_request_detaches_network_tracker():
    page = FakePage()
    searcher = make_patchright(page)
    search(searcher)
    assert searcher.network is None
    assert all(not handlers for handlers in page.handlers.values())


# Network tracker ---------------------------------------------------------------


def test_tracker_idle_after_quiet_period():
    page = FakePage()
    tracker = NetworkTracker(page)
    assert tracker.wait_for_idle(5_000) is True
    assert FakeClock.now == pytest.approx(IDLE_MS / 1000, abs=0.11)


def test_tracker_ignores_speculative_prefetch():
    page = FakePage()
    tracker = NetworkTracker(page)
    page.emit("request", FakeRequest("https://www.google.com/goto?url=x", prefetch=True))
    assert tracker.wait_for_idle(5_000) is True
    assert not tracker.inflight


def test_tracker_busy_until_request_ends():
    page = FakePage()
    tracker = NetworkTracker(page)
    request = FakeRequest("https://www.google.com/async/folsrch")
    page.emit("request", request)
    assert tracker.wait_for_idle(2_000) is False
    page.emit("requestfailed", request)
    assert tracker.wait_for_idle(2_000) is True


def test_tracker_detach_removes_handlers():
    page = FakePage()
    tracker = NetworkTracker(page)
    tracker.detach()
    page.emit("request", FakeRequest("https://www.google.com/async/folsrch"))
    assert not tracker.inflight


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
