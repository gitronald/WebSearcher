"""The patchright backend's network tracker in a real browser (plan 066).

A local server's page prefetches a URL that never answers, through speculation
rules as a SERP does with its top results. The tracker must treat that page as
quiet, while a plain request it starts keeps the page busy until it answers.
Runs headless against 127.0.0.1 only, and skips when Chrome is unavailable.
"""

import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, override

import pytest

from WebSearcher.searchers.patchright_searcher import IDLE_MS, NetworkTracker

FETCH_HOLD_S = 1.5

PREFETCH_PAGE = b"""<!doctype html><html><head><title>prefetch</title>
<script type="speculationrules">{"prefetch": [{"urls": ["/hang"]}]}</script>
</head><body><a href="/hang">result</a></body></html>"""

FETCH_PAGE = b"""<!doctype html><html><head><title>fetch</title></head>
<body><script>fetch("/held")</script></body></html>"""


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    release = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/hang":
                release.wait(30)
            elif self.path == "/held":
                time.sleep(FETCH_HOLD_S)
            body = {"/prefetch": PREFETCH_PAGE, "/fetch": FETCH_PAGE}.get(self.path, b"ok")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                pass  # the browser gave up on the request

        @override
        def log_message(self, format: str, *args: Any) -> None:
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    release.set()
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    from patchright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    try:
        chrome = playwright.chromium.launch(channel="chrome", headless=True)
    except Exception as e:
        playwright.stop()
        pytest.skip(f"Chrome unavailable for patchright: {e}")
    yield chrome
    chrome.close()
    playwright.stop()


def _load(browser: Any, url: str, seen: list[Any]) -> tuple[Any, NetworkTracker, float]:
    page = browser.new_page()
    page.on("request", lambda request: seen.append(request))
    tracker = NetworkTracker(page)
    start = time.monotonic()
    page.goto(url, wait_until="load")
    return page, tracker, start


def test_tracker_ignores_hanging_prefetch(server, browser):
    seen: list[Any] = []
    page, tracker, start = _load(browser, f"{server}/prefetch", seen)
    try:
        assert tracker.wait_for_idle(5_000) is True
        assert time.monotonic() - start < 2.0
        # The prefetch was made, and is still open: the page was quiet despite it
        prefetches = [r for r in seen if r.url.endswith("/hang")]
        assert [r.headers.get("sec-purpose") for r in prefetches] == ["prefetch"]
    finally:
        tracker.detach()
        page.close()


def test_tracker_waits_for_plain_request(server, browser):
    page, tracker, start = _load(browser, f"{server}/fetch", [])
    try:
        assert tracker.wait_for_idle(5_000) is True
        assert time.monotonic() - start >= FETCH_HOLD_S + IDLE_MS / 1000 - 0.1
    finally:
        tracker.detach()
        page.close()
