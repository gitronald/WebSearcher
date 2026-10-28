"""Tests for the patchright backend's send_request failure-path capture.

The backend is driven with fake page objects so no browser is needed. Two
behaviors are pinned: a navigation that lands somewhere (e.g. a /sorry/ CAPTCHA
redirect) but then times out on #search still captures the live URL and HTML; a
failure *before* navigation captures nothing, so the previous query's page is
never recorded under the new query.
"""

import gc
import logging
import subprocess
import sys
import textwrap
import weakref

from WebSearcher.models.configs import PatchrightConfig
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
    """The page holds the previous SERP; the search's goto raises before navigating."""

    def __init__(self):
        self.url = PREV_URL

    def goto(self, url, wait_until=None, timeout=None):
        if url == "about:blank":
            self.url = url
            return None
        raise Exception("net::ERR_CONNECTION_RESET")


def make_patchright(page) -> PatchrightSearcher:
    searcher = PatchrightSearcher.__new__(PatchrightSearcher)
    searcher.config = PatchrightConfig()
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


def test_patchright_block_logs_no_error(monkeypatch, caplog):
    # A /sorry/ block is reported by SearchEngine as a captcha event, not as a
    # backend error with a traceback.
    monkeypatch.setattr("WebSearcher.searchers.patchright_searcher.time.sleep", lambda s: None)
    with caplog.at_level(logging.DEBUG, logger=LOG.name):
        make_patchright(FakePageBlocked()).send_request(SearchParams.create({"qry": "test"}))
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_patchright_nav_failure_logs_error(monkeypatch, caplog):
    monkeypatch.setattr("WebSearcher.searchers.patchright_searcher.time.sleep", lambda s: None)
    with caplog.at_level(logging.DEBUG, logger=LOG.name):
        make_patchright(FakePageNavFails()).send_request(SearchParams.create({"qry": "test"}))
    assert [r for r in caplog.records if r.levelno == logging.ERROR]


# Exit hook --------------------------------------------------------------------


class FakeContext:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakePlaywright:
    def stop(self):
        pass


def make_open_patchright() -> PatchrightSearcher:
    """A searcher that looks launched (fake context/driver), with its exit hook."""
    searcher = make_patchright(None)
    searcher.playwright = FakePlaywright()
    searcher.context = FakeContext()
    searcher._tmp_profile = ""
    searcher._exit_hook = None
    searcher._register_exit_hook()
    return searcher


def test_exit_hook_closes_open_searcher():
    searcher = make_open_patchright()
    context = searcher.context
    hook = searcher._exit_hook
    assert hook is not None
    hook()
    assert context.closed
    assert searcher.playwright is None


def test_cleanup_unregisters_exit_hook(monkeypatch):
    unregistered = []
    monkeypatch.setattr(
        "WebSearcher.searchers.patchright_searcher.atexit.unregister", unregistered.append
    )
    searcher = make_open_patchright()
    hook = searcher._exit_hook
    searcher.cleanup()
    assert unregistered == [hook]
    assert searcher._exit_hook is None


def test_exit_hook_does_not_keep_searcher_alive():
    searcher = make_open_patchright()
    hook = searcher._exit_hook
    assert hook is not None
    ref = weakref.ref(searcher)
    del searcher
    gc.collect()
    assert ref() is None
    hook()  # the searcher is gone: a no-op, not an error


def test_exit_hook_runs_at_interpreter_exit():
    # The real atexit path, in a fresh interpreter that exits without cleanup().
    script = textwrap.dedent(
        """
        import logging
        from WebSearcher.searchers.patchright_searcher import PatchrightSearcher

        class Context:
            def close(self):
                print("context closed", flush=True)

        class Playwright:
            def stop(self):
                print("playwright stopped", flush=True)

        searcher = PatchrightSearcher.__new__(PatchrightSearcher)
        searcher.log = logging.getLogger("exit-hook-test")
        searcher.playwright = Playwright()
        searcher.context = Context()
        searcher.page = None
        searcher._tmp_profile = ""
        searcher._exit_hook = None
        searcher._register_exit_hook()
        """
    )
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == ["context closed", "playwright stopped"]
    assert out.stderr == ""
