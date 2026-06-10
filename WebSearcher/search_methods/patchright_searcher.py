"""Proof-of-concept patchright backend (plan 039) — "undetected" Playwright fork.

Uses the sync API with a persistent context on the system Chrome channel, the
setup patchright documents as its stealth baseline. Lifecycle is fully
deterministic: ``context.close()`` + ``playwright.stop()``.
"""

import shutil
import tempfile
import time
from datetime import UTC, datetime
from typing import Any

import orjson

from .. import utils
from ..models.configs import PatchrightConfig
from ..models.data import ResponseOutput
from ..models.searches import SearchParams

# CSS equivalents of the selenium backend's AI-overview XPaths
SHOW_MORE_SELECTOR = 'div[jsname="rPRdsc"][role="button"]'
SHOW_ALL_SELECTOR = 'div.trEk7e[role="button"]'


class PatchrightSearcher:
    """Handle patchright-based web interactions for search engines"""

    driver_name = "patchright"

    def __init__(self, config: PatchrightConfig, logger):
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

    def _start_playwright(self) -> Any:
        from patchright.sync_api import sync_playwright

        return sync_playwright().start()

    def init_driver(self) -> None:
        """Launch Chrome via patchright with a persistent context"""
        user_data_dir = self.config.user_data_dir
        if not user_data_dir:
            self._tmp_profile = tempfile.mkdtemp(prefix="ws-patchright-")
            user_data_dir = self._tmp_profile

        self.log.debug(
            f"SERP | init {self.driver_name} | channel: {self.config.channel} | "
            f"headless: {self.config.headless} | user_data_dir: {user_data_dir}"
        )
        self.playwright = self._start_playwright()
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel=self.config.channel,
            headless=self.config.headless,
            no_viewport=True,
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
        self.log.debug(orjson.dumps(self.browser_info, option=orjson.OPT_INDENT_2))

    def send_request(self, search_params: SearchParams) -> ResponseOutput:
        """Visit a URL with patchright and save HTML response"""

        response_output = ResponseOutput(
            url=search_params.url,
            user_agent=self.browser_info.get("user_agent", ""),
            timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat(),
        )

        try:
            response = self.page.goto(search_params.url, wait_until="domcontentloaded")
            time.sleep(2)
            self.page.wait_for_selector("#search", timeout=10_000)
            time.sleep(2)
            response_output.html = self.page.content()
            response_output.url = self.page.url
            response_output.response_code = response.status if response else 200

            # Expand AI overview if requested
            if search_params.ai_expand:
                expanded_html = self.expand_ai_overview()
                if expanded_html:
                    len_diff = len(expanded_html) - len(response_output.html)
                    self.log.debug(f"SERP | expanded html | len diff: {len_diff}")
                    response_output.html = expanded_html

        except Exception as e:
            self.log.exception(f"SERP | Patchright error | {str(e)}")
        finally:
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
            self.log.debug("Browser successfully closed")
            return True
        except Exception as e:
            self.log.debug(f"Browser already closed or unreachable: {e}")
            return False
        finally:
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
                self.log.debug(f"Failed to delete cookies: {str(e)}")

    def __del__(self):
        """Destructor to ensure browser is closed when object is garbage collected"""
        try:
            self.cleanup()
        except Exception:
            pass


class PlaywrightSearcher(PatchrightSearcher):
    """Plain-playwright variant of the patchright PoC — same contract and config,
    unpatched upstream driver. Exists to test whether patchright's stealth patches
    are actually needed for Google SERPs."""

    driver_name = "playwright"

    def _start_playwright(self) -> Any:
        from playwright.sync_api import sync_playwright

        return sync_playwright().start()
