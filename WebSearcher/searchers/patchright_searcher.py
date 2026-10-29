"""Patchright browser backend — an "undetected" Playwright fork (plan 039).

The default browser backend (plan 051). Uses the sync API with a persistent
context on the system Chrome channel, the setup patchright documents as its
stealth baseline. Lifecycle is fully deterministic: ``context.close()`` +
``playwright.stop()``.
"""

import atexit
import functools
import logging
import shutil
import tempfile
import time
import weakref
from collections.abc import Callable
from pathlib import Path
from typing import Any

import orjson

from .. import utils
from ..models.configs import PatchrightConfig
from ..models.data import ResponseOutput
from ..models.searches import SearchParams

# CSS selectors for the AI-overview expand controls
SHOW_MORE_SELECTOR = 'div[jsname="rPRdsc"][role="button"]'
SHOW_MORE_EXPANDED_SELECTOR = f'{SHOW_MORE_SELECTOR}[aria-expanded="true"]'
SHOW_ALL_SELECTOR = 'div.trEk7e[role="button"]'

# An AI overview's container while its answer is still generating. The page's
# script sets data-loaded="1" once the answer has streamed in. data-attnms leaves
# "l" about a second in, while a conversational overview still reads "Thinking",
# so it does not mark the end.
AI_OVERVIEW_PENDING_SELECTOR = 'div[jscontroller="EYwa3d"]:not([data-loaded="1"])'

# Capture timing (ms). A SERP can replace itself once more after #search first
# renders, and a streamed AI overview keeps loading for a few seconds after it
# (plan 066), so a capture waits for load, then for any AI overview to finish,
# then for the network to go quiet. The overview wait starts once the page has
# loaded, and its cap is about three times the slowest overview seen (done about
# 5 s from goto, for "Tell me about" queries); a page without a pending overview
# skips it. The quiet wait is capped because a
# page's background requests can keep it busy. Its cap is about twice the latest
# stream end seen (about 4.2 s from goto); it costs time only on a page still
# busy at the cap.
SEARCH_TIMEOUT_MS = 10_000
LOAD_TIMEOUT_MS = 5_000
AI_OVERVIEW_TIMEOUT_MS = 15_000
NETWORKIDLE_TIMEOUT_MS = 8_000
RESET_TIMEOUT_MS = 5_000
EXPAND_TIMEOUT_MS = 5_000

# The network is quiet after this long with no request in flight (the driver's
# own networkidle rule), checked every IDLE_POLL_MS
IDLE_MS = 500
IDLE_POLL_MS = 100

# Attempts at page.content() while the page is still navigating
CONTENT_ATTEMPTS = 3


def _is_navigating_error(e: Exception) -> bool:
    """Whether ``e`` is the error ``page.content()`` raises mid-navigation."""
    return "page is navigating" in str(e)


def _is_prefetch(request: Any) -> bool:
    """Whether ``request`` is a speculative prefetch (``Sec-Purpose: prefetch``).

    A SERP's speculation rules prefetch its top results' links, and Chrome can
    hold such a request open for about 10 s before dropping it.
    """
    return "prefetch" in request.headers.get("sec-purpose", "")


class NetworkTracker:
    """Track a page's requests in flight, ignoring speculative prefetches.

    Stands in for the driver's ``networkidle``, which counts a prefetch that
    never finishes and then runs to its timeout on about a fifth of SERPs
    (plan 066).
    Attach before navigating: a request started earlier is not tracked.
    """

    def __init__(self, page: Any) -> None:
        self.page = page
        self.inflight: set[Any] = set()
        self.last_change = time.monotonic()
        self._handlers: dict[str, Callable[[Any], None]] = {
            "request": self._started,
            "requestfinished": self._ended,
            "requestfailed": self._ended,
        }
        for event, handler in self._handlers.items():
            page.on(event, handler)

    def _started(self, request: Any) -> None:
        if _is_prefetch(request):
            return
        self.inflight.add(request)
        self.last_change = time.monotonic()

    def _ended(self, request: Any) -> None:
        if request in self.inflight:
            self.inflight.discard(request)
            self.last_change = time.monotonic()

    def wait_for_idle(self, timeout_ms: int) -> bool:
        """Wait until no request has been in flight for ``IDLE_MS``.

        Returns ``False`` when ``timeout_ms`` passes first. Waits with
        ``page.wait_for_timeout``, which delivers the request events.
        """
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            now = time.monotonic()
            if not self.inflight and now - self.last_change >= IDLE_MS / 1000:
                return True
            if now >= deadline:
                return False
            self.page.wait_for_timeout(IDLE_POLL_MS)

    def detach(self) -> None:
        for event, handler in self._handlers.items():
            self.page.remove_listener(event, handler)


def prepare_profile_dir(path: Path) -> None:
    """Create a new persistent profile dir that git ignores.

    A profile holds cookies and session tokens, so a new one gets a ``.gitignore``
    of ``*`` (as ``.pytest_cache`` does) and stays out of any repo it sits in. An
    existing directory is left untouched.
    """
    if path.exists():
        return
    path.mkdir(parents=True)
    (path / ".gitignore").write_text("# Browser profile created by WebSearcher\n*\n")


def _cleanup_at_exit(ref: "weakref.ref[PatchrightSearcher]") -> None:
    """Close a searcher still open at interpreter exit (registered by ``init_driver``)."""
    searcher = ref()
    if searcher is not None:
        searcher.cleanup()


class PatchrightSearcher:
    """Handle patchright-based web interactions for search engines"""

    driver_name = "patchright"

    def __init__(self, config: PatchrightConfig, logger: logging.Logger):
        """Initialize a patchright searcher with the given configuration

        Args:
            config (PatchrightConfig): Configuration for patchright
            logger: Logger instance
        """
        self.config = config
        self.log = logger
        self.playwright: Any = None
        self.context: Any = None
        self.page: Any = None
        self.browser_info: dict[str, str] = {}
        self._tmp_profile: str = ""
        self._exit_hook: Callable[[], None] | None = None
        self.network: NetworkTracker | None = None

    def init_driver(self) -> None:
        """Launch Chrome via patchright with a persistent context"""
        if self.config.user_data_dir:
            profile = Path(self.config.user_data_dir).expanduser()
            prepare_profile_dir(profile)
            user_data_dir = str(profile)
        else:
            self._tmp_profile = tempfile.mkdtemp(prefix="ws-patchright-")
            user_data_dir = self._tmp_profile

        self.log.debug(
            f"SERP | init {self.driver_name} | channel: {self.config.channel} | "
            f"headless: {self.config.headless} | user_data_dir: {user_data_dir}",
            extra={"event": "init_driver"},
        )
        from patchright.sync_api import sync_playwright

        try:
            self.playwright = sync_playwright().start()
            self._register_exit_hook()
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel=self.config.channel,
                headless=self.config.headless,
                no_viewport=True,
                chromium_sandbox=self.config.chromium_sandbox,
            )
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            user_agent = self.page.evaluate("navigator.userAgent")
        except Exception:
            # Driver failed to start, Chrome missing, profile locked, ...: close
            # whatever did start and drop the temp profile now rather than
            # leaving them to the exit hook.
            self.cleanup()
            raise

        browser_version = ""
        if self.context.browser is not None:
            browser_version = self.context.browser.version
        self.browser_info = {
            "browser_id": "",
            "browser_name": self.config.channel,
            "browser_version": browser_version,
            "driver_version": self.driver_name,
            "user_agent": user_agent,
        }
        self.browser_info["browser_id"] = utils.hash_id(
            orjson.dumps(self.browser_info).decode("utf-8")
        )
        self.log.debug(
            orjson.dumps(self.browser_info, option=orjson.OPT_INDENT_2).decode("utf-8"),
            extra={"event": "browser_info"},
        )

    def send_request(self, search_params: SearchParams) -> ResponseOutput:
        """Visit a URL with patchright and save HTML response"""

        response_output = ResponseOutput(
            url=search_params.url,
            user_agent=self.browser_info.get("user_agent", ""),
            timestamp=utils.utc_timestamp(),
        )

        pre_nav_url: str | None = None
        try:
            # Start from a blank page, so a late navigation of the previous SERP
            # cannot land in this request, and the "URL moved" check below never
            # takes the previous query's SERP for this one.
            self.reset_page()
            pre_nav_url = self.page.url
            self.network = NetworkTracker(self.page)
            response = self.page.goto(search_params.url, wait_until="domcontentloaded")
            # Record the status before the #search wait so a blocked request
            # (e.g. 429 on a /sorry/ redirect) keeps its real code on timeout.
            response_output.response_code = response.status if response else 200
            self.page.wait_for_selector("#search", timeout=SEARCH_TIMEOUT_MS)
            self.settle_page()
            response_output.html = self.page_content()
            response_output.url = self.page.url
            if not response_output.has_search:
                self.log.warning(
                    f"SERP | {self.driver_name} | captured HTML has no #search",
                    extra={"event": "capture", "qry": search_params.qry, "loc": search_params.loc},
                )

            # Expand AI overview if requested
            if search_params.ai_expand:
                expanded_html = self.expand_ai_overview()
                if expanded_html:
                    len_diff = len(expanded_html) - len(response_output.html)
                    self.log.debug(
                        f"SERP | expanded html | len diff: {len_diff}",
                        extra={"event": "ai_expand"},
                    )
                    response_output.html = expanded_html

        except Exception as e:
            # Capture the live URL and whatever HTML rendered anyway -- a
            # CAPTCHA challenge redirects to /sorry/ and never shows #search,
            # so the redirect would otherwise be discarded with the timeout.
            # Only when the URL moved off the pre-navigation page: a failure
            # before navigation would otherwise record the previous query's SERP.
            if self.page is not None and pre_nav_url is not None:
                try:
                    live_url = self.page.url
                    if live_url and live_url != pre_nav_url:
                        response_output.url = live_url
                        response_output.html = self.page_content(require_search=False)
                except Exception:
                    pass
            if utils.is_sorry_redirect(response_output.url):
                # A block, not a fault: SearchEngine.search logs it as a captcha event.
                self.log.debug(
                    f"SERP | {self.driver_name} | /sorry/ redirect | {str(e)}",
                    extra={"event": "fetch"},
                )
            else:
                self.log.exception(
                    f"SERP | {self.driver_name} error | {str(e)}", extra={"event": "fetch"}
                )
        finally:
            if self.network is not None:
                self.network.detach()
                self.network = None
            if self.config.clear_cookies:
                self.delete_cookies()

        return response_output

    def reset_page(self) -> None:
        """Park the page on ``about:blank``, or replace it when that fails.

        The blank-page navigation fails when the previous SERP navigates over
        it ("interrupted by another navigation"); a new page in the same context
        then drops the old one.
        """
        if self.page.url == "about:blank":
            return
        try:
            self.page.goto("about:blank", wait_until="load", timeout=RESET_TIMEOUT_MS)
            if self.page.url == "about:blank":
                return
        except Exception as e:
            self.log.debug(f"SERP | blank-page reset failed | {e}", extra={"event": "reset_page"})
        self.log.debug("SERP | replacing page", extra={"event": "reset_page"})
        self.page.close()
        self.page = self.context.new_page()

    def settle_page(self, require_search: bool = True) -> None:
        """Wait for load, any AI overview, and a quiet network, then confirm ``#search``.

        Each wait is bounded and its timeout ignored: a page's background
        requests can keep the network busy, and a late capture beats none. The
        quiet wait needs the request's ``NetworkTracker``, so it is skipped
        outside ``send_request``.
        """
        try:
            self.page.wait_for_load_state("load", timeout=LOAD_TIMEOUT_MS)
        except Exception:
            pass
        self.wait_for_ai_overview()
        if self.network is not None and not self.network.wait_for_idle(NETWORKIDLE_TIMEOUT_MS):
            self.log.debug(
                f"SERP | network busy at cap | {len(self.network.inflight)} in flight",
                extra={"event": "capture"},
            )
        if require_search:
            self.page.wait_for_selector("#search", state="attached", timeout=SEARCH_TIMEOUT_MS)

    def wait_for_ai_overview(self) -> None:
        """Wait until no AI overview on the page is still generating, up to its cap.

        Returns at once when none is pending. Otherwise logs an ``ai_wait`` event:
        how long the overview took to load, or that the cap passed (its answer
        will parse as ``not_loaded``). A failed check ends the wait.
        """
        try:
            pending = self.page.locator(AI_OVERVIEW_PENDING_SELECTOR)
            if pending.count() == 0:
                return
            start = time.monotonic()
            deadline = start + AI_OVERVIEW_TIMEOUT_MS / 1000
            while pending.count():
                if time.monotonic() >= deadline:
                    self.log.debug(
                        "SERP | ai overview not loaded at cap", extra={"event": "ai_wait"}
                    )
                    return
                self.page.wait_for_timeout(IDLE_POLL_MS)
            self.log.debug(
                f"SERP | ai overview loaded | {time.monotonic() - start:.2f} s",
                extra={"event": "ai_wait"},
            )
        except Exception as e:
            self.log.debug(f"SERP | ai overview check failed | {e}", extra={"event": "ai_wait"})

    def page_content(self, require_search: bool = True) -> str:
        """Return ``page.content()``, retrying while the page is navigating.

        Only the "page is navigating" error is retried: each retry backs off,
        settles the page again, and (with ``require_search``) re-checks ``#search``.
        """
        for attempt in range(1, CONTENT_ATTEMPTS + 1):
            try:
                return self.page.content()
            except Exception as e:
                if attempt == CONTENT_ATTEMPTS or not _is_navigating_error(e):
                    raise
                self.log.debug(
                    f"SERP | page navigating during capture | attempt {attempt}",
                    extra={"event": "capture"},
                )
                time.sleep(0.5 * attempt)
                self.settle_page(require_search)
        raise AssertionError("unreachable")

    def expand_ai_overview(self) -> str | None:
        """Expand the AI overview by clicking its show-more control.

        Returns the expanded HTML, or ``None`` when nothing was expanded. The
        outcome is logged as an ``ai_expand`` event: ``expanded``, ``unconfirmed``
        (clicked, but the control has no ``aria-expanded`` to confirm it),
        ``not_expanded`` (clicked, and ``aria-expanded`` stayed false),
        ``no_control``, ``click_failed``, or ``capture_failed``.
        """
        show_more = self.page.locator(SHOW_MORE_SELECTOR).first
        try:
            if show_more.count() == 0:
                return self._ai_expand_outcome("no_control")
            confirmable = (
                show_more.get_attribute("aria-expanded", timeout=EXPAND_TIMEOUT_MS) is not None
            )
            show_more.click(timeout=EXPAND_TIMEOUT_MS)
        except Exception:
            return self._ai_expand_outcome("click_failed")

        if confirmable:
            try:
                self.page.wait_for_selector(
                    SHOW_MORE_EXPANDED_SELECTOR, state="attached", timeout=EXPAND_TIMEOUT_MS
                )
            except Exception:
                return self._ai_expand_outcome("not_expanded")
            outcome = "expanded"
        else:
            time.sleep(2)  # Nothing to wait on: give the added content time to load
            outcome = "unconfirmed"

        try:
            self.page.locator(SHOW_ALL_SELECTOR).first.click(timeout=1_000)
        except Exception:
            pass

        try:
            html = self.page_content(require_search=False)
        except Exception:
            return self._ai_expand_outcome("capture_failed")
        self._ai_expand_outcome(outcome)
        return html

    def _ai_expand_outcome(self, outcome: str) -> None:
        self.log.debug(f"SERP | ai_expand | {outcome}", extra={"event": "ai_expand"})

    def _register_exit_hook(self) -> None:
        """Close this searcher at interpreter exit if it is still open then.

        ``__del__`` is not guaranteed to run at exit, and when it does,
        patchright's event loop is already gone, so the close never completes
        and the temp profile is left behind. ``atexit`` runs while the
        interpreter is intact. The hook holds a weak reference, so it never
        keeps a dropped searcher alive; ``cleanup`` unregisters it.
        """
        self._exit_hook = functools.partial(_cleanup_at_exit, weakref.ref(self))
        atexit.register(self._exit_hook)

    def cleanup(self) -> bool:
        """Close the context and stop playwright.

        ``context.close()`` ends the browser process and ``playwright.stop()``
        shuts down the driver transport, so teardown is deterministic. A temp
        profile directory created by ``init_driver`` is removed afterwards, also
        when the driver never started.
        """
        if not self.playwright:
            self._remove_tmp_profile()
            return True

        try:
            # Stop the driver even when closing the context fails (Chrome already
            # crashed or was closed by hand), or its node process is orphaned.
            try:
                if self.context is not None:
                    self.context.close()
            finally:
                self.playwright.stop()
            self.log.debug("Browser successfully closed", extra={"event": "cleanup"})
            return True
        except Exception as e:
            self.log.debug(
                f"Browser already closed or unreachable: {e}", extra={"event": "cleanup"}
            )
            return False
        finally:
            if self._exit_hook is not None:
                atexit.unregister(self._exit_hook)
                self._exit_hook = None
            self.playwright = None
            self.context = None
            self.page = None
            self._remove_tmp_profile()

    def _remove_tmp_profile(self) -> None:
        if self._tmp_profile:
            shutil.rmtree(self._tmp_profile, ignore_errors=True)
            self._tmp_profile = ""

    def delete_cookies(self):
        """Delete all cookies from the browser"""
        if self.context:
            try:
                self.context.clear_cookies()
            except Exception as e:
                self.log.debug(
                    f"Failed to delete cookies: {str(e)}", extra={"event": "delete_cookies"}
                )

    def __del__(self):
        """Destructor to ensure browser is closed when object is garbage collected"""
        try:
            self.cleanup()
        except Exception:
            pass
