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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from .. import utils
from ..models.configs import PatchrightConfig
from ..models.data import ResponseOutput
from ..models.searches import SearchParams

# CSS selectors for the AI-overview expand controls
SHOW_MORE_SELECTOR = 'div[jsname="rPRdsc"][role="button"]'
SHOW_ALL_SELECTOR = 'div.trEk7e[role="button"]'


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

        browser_version = ""
        if self.context.browser is not None:
            browser_version = self.context.browser.version
        self.browser_info = {
            "browser_id": "",
            "browser_name": self.config.channel,
            "browser_version": browser_version,
            "driver_version": self.driver_name,
            "user_agent": self.page.evaluate("navigator.userAgent"),
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
            timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat(),
        )

        pre_nav_url: str | None = None
        try:
            pre_nav_url = self.page.url
            response = self.page.goto(search_params.url, wait_until="domcontentloaded")
            # Record the status before the #search wait so a blocked request
            # (e.g. 429 on a /sorry/ redirect) keeps its real code on timeout.
            response_output.response_code = response.status if response else 200
            time.sleep(2)
            self.page.wait_for_selector("#search", timeout=10_000)
            time.sleep(2)
            response_output.html = self.page.content()
            response_output.url = self.page.url

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
                        response_output.html = self.page.content()
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
            if self.config.clear_cookies:
                self.delete_cookies()

        return response_output

    def expand_ai_overview(self):
        """Expand AI overview box by clicking it"""
        show_more_button = self.page.locator(SHOW_MORE_SELECTOR).first
        try:
            show_more_button.click(timeout=1_000)
        except Exception:
            return None

        time.sleep(2)  # Wait for additional content to load
        try:
            self.page.locator(SHOW_ALL_SELECTOR).first.click(timeout=1_000)
        except Exception:
            pass

        try:
            return self.page.content()
        except Exception:
            return None

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
        profile directory created by ``init_driver`` is removed afterwards.
        """
        if not self.playwright:
            return True

        try:
            if self.context is not None:
                self.context.close()
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
