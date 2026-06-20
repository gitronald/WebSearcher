"""Proof-of-concept zendriver backend (plan 039) — async CDP, no selenium/webdriver.

zendriver is the maintained fork of nodriver (the undetected_chromedriver author's
successor); nodriver itself is import-broken on recent releases (>=0.48 ships a
non-UTF-8 byte in cdp/network.py). The async API is wrapped in a dedicated event
loop so this mirrors the synchronous ``SeleniumDriver`` contract.
"""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import orjson

from .. import utils
from ..models.configs import ZendriverConfig
from ..models.data import ResponseOutput
from ..models.searches import SearchParams

# CSS equivalents of the selenium backend's AI-overview XPaths
SHOW_MORE_SELECTOR = 'div[jsname="rPRdsc"][role="button"]'
SHOW_ALL_SELECTOR = 'div.trEk7e[role="button"]'


class ZendriverSearcher:
    """Handle zendriver-based web interactions for search engines"""

    def __init__(self, config: ZendriverConfig, logger):
        """Initialize a zendriver searcher with the given configuration

        Args:
            config (ZendriverConfig): Configuration for zendriver
            logger: Logger instance
        """
        self.config = config
        self.log = logger
        self.browser: Any = None
        self.tab: Any = None
        self.browser_info: dict[str, str] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def _run(self, coro):
        """Run a coroutine on this searcher's dedicated event loop"""
        if self._loop is None:
            raise RuntimeError("Zendriver not initialized; call init_driver() first")
        return self._loop.run_until_complete(coro)

    def init_driver(self) -> None:
        """Start the browser with zendriver-specific config"""
        import zendriver

        self._loop = asyncio.new_event_loop()
        kwargs: dict[str, Any] = {"headless": self.config.headless}
        if self.config.browser_executable_path:
            kwargs["browser_executable_path"] = self.config.browser_executable_path
        self.log.debug(f"SERP | init zendriver | kwargs: {kwargs}")
        self.browser = self._run(zendriver.start(**kwargs))
        self.tab = self._run(self.browser.get("about:blank"))

        self.browser_info = {
            "browser_id": "",
            "browser_name": "chrome-cdp",
            "browser_version": self.browser.info.get("Browser", "") if self.browser.info else "",
            "driver_version": f"zendriver {zendriver.__version__}",
            "user_agent": self._run(self.tab.evaluate("navigator.userAgent")),
        }
        self.browser_info["browser_id"] = utils.hash_id(
            orjson.dumps(self.browser_info).decode("utf-8")
        )
        self.log.debug(orjson.dumps(self.browser_info, option=orjson.OPT_INDENT_2))

    def send_request(self, search_params: SearchParams) -> ResponseOutput:
        """Visit a URL with zendriver and save HTML response"""

        response_output = ResponseOutput(
            url=search_params.url,
            user_agent=self.browser_info.get("user_agent", ""),
            timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat(),
        )

        pre_nav_url: str | None = None
        try:
            if self.tab is not None:
                pre_nav_url = self.tab.url  # local target info, no CDP round-trip
            self.tab = self._run(self.browser.get(search_params.url))
            time.sleep(2)
            self._run(self.tab.select("#search", timeout=10))
            time.sleep(2)
            response_output.html = self._run(self.tab.get_content())
            response_output.url = self._run(self.tab.evaluate("window.location.href"))
            response_output.response_code = 200

            # Expand AI overview if requested
            if search_params.ai_expand:
                expanded_html = self.expand_ai_overview()
                if expanded_html:
                    len_diff = len(expanded_html) - len(response_output.html)
                    self.log.debug(f"SERP | expanded html | len diff: {len_diff}")
                    response_output.html = expanded_html

        except Exception as e:
            self.log.exception(f"SERP | Zendriver error | {str(e)}")
            # Capture the live URL and whatever HTML rendered anyway -- a
            # CAPTCHA challenge redirects to /sorry/ and never shows #search,
            # so the redirect would otherwise be discarded with the timeout.
            # Only when the URL moved off the pre-navigation page: a failure
            # before navigation would otherwise record the previous query's SERP.
            if self.tab is not None and pre_nav_url is not None:
                try:
                    live_url = self.tab.url  # local target info, no CDP round-trip
                    if live_url and live_url != pre_nav_url:
                        response_output.url = live_url
                        response_output.html = self._run(self.tab.get_content())
                except Exception:
                    pass
        finally:
            self.delete_cookies()

        return response_output

    def expand_ai_overview(self):
        """Expand AI overview box by clicking it"""
        try:
            show_more_button = self._run(self.tab.select(SHOW_MORE_SELECTOR, timeout=1))
        except Exception:
            return None

        try:
            self._run(show_more_button.click())
            time.sleep(2)  # Wait for additional content to load
            try:
                show_all_button = self._run(self.tab.select(SHOW_ALL_SELECTOR, timeout=1))
                self._run(show_all_button.click())
            except Exception:
                pass
            return self._run(self.tab.get_content())
        except Exception:
            return None

    def cleanup(self) -> bool:
        """Stop the browser and close the event loop.

        ``Browser.stop()`` is a coroutine that terminates the chrome process and
        closes the CDP websocket, so teardown is deterministic — no leaked
        chromedriver session to race interpreter exit.
        """
        if not self.browser:
            return True

        try:
            self._run(self.browser.stop())
            self.log.debug("Browser successfully closed")
            return True
        except Exception as e:
            self.log.debug(f"Browser already closed or unreachable: {e}")
            return False
        finally:
            if self._loop is not None:
                self._loop.close()
                self._loop = None
            self.browser = None
            self.tab = None

    def delete_cookies(self):
        """Delete all cookies from the browser"""
        if self.browser:
            try:
                self._run(self.browser.cookies.clear())
            except Exception as e:
                self.log.debug(f"Failed to delete cookies: {str(e)}")

    def __del__(self):
        """Destructor to ensure browser is closed when object is garbage collected"""
        try:
            self.cleanup()
        except Exception:
            pass
