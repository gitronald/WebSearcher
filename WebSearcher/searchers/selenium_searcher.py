import logging
import re
import subprocess
import time
from datetime import UTC, datetime

import orjson
import undetected_chromedriver as uc
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .. import utils
from ..models.configs import SeleniumConfig
from ..models.data import ResponseOutput
from ..models.searches import SearchParams


def detect_chrome_version() -> str | None:
    """Detect the full version of the installed Chrome/Chromium browser.

    Returns the version string (e.g. "148.0.7778.179") or None if it can't be
    determined.
    """
    chrome_path = uc.find_chrome_executable()
    if not chrome_path:
        return None
    try:
        output = subprocess.check_output(
            [chrome_path, "--version"], stderr=subprocess.STDOUT, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"\b(\d+\.\d+\.\d+(?:\.\d+)?)\b", output)
    return match.group(1) if match else None


def detect_chrome_major_version() -> int | None:
    """Detect the major version of the installed Chrome/Chromium browser.

    Returns the major version (e.g. 148) or None if it can't be determined.
    """
    version = detect_chrome_version()
    return int(version.split(".")[0]) if version else None


class SeleniumDriver:
    """Handle Selenium-based web interactions for search engines"""

    def __init__(self, config: SeleniumConfig, logger):
        """Initialize a Selenium driver with the given configuration

        Args:
            config (SeleniumConfig): Configuration for Selenium
            logger: Logger instance
        """
        self.config = config
        self.log = logger
        self.driver: uc.Chrome | None = None
        self.browser_info: dict[str, str] = {}

    def _require_driver(self) -> uc.Chrome:
        if self.driver is None:
            raise RuntimeError("Selenium driver not initialized; call init_driver() first")
        return self.driver

    def init_driver(self) -> None:
        """Initialize Chrome driver with selenium-specific config"""
        if self.config.version_main is None:
            detected = detect_chrome_major_version()
            if detected is not None:
                self.config.version_main = detected
                self.log.debug(f"SERP | detected chrome major version | {detected}")
            else:
                self.log.warning("SERP | could not detect chrome version; using uc default")
        self.log.debug(f"SERP | init uc chromedriver | kwargs: {self.config.__dict__}")
        self.driver = uc.Chrome(**self.config.__dict__)

        # Log version information
        self.browser_info = {
            "browser_id": "",
            "browser_name": self.driver.capabilities["browserName"],
            "browser_version": self.driver.capabilities["browserVersion"],
            "driver_version": self.driver.capabilities["chrome"]["chromedriverVersion"].split(" ")[
                0
            ],
            "user_agent": self.driver.execute_script("return navigator.userAgent"),
        }
        self.browser_info["browser_id"] = utils.hash_id(
            orjson.dumps(self.browser_info).decode("utf-8")
        )
        self.log.debug(orjson.dumps(self.browser_info, option=orjson.OPT_INDENT_2))

    def send_typed_query(self, query: str):
        """Send a typed query to the search box"""
        driver = self._require_driver()
        time.sleep(2)
        driver.get("https://www.google.com")
        time.sleep(2)
        search_box = driver.find_element(By.ID, "APjFqb")
        search_box.clear()
        search_box.send_keys(query)
        search_box.send_keys(Keys.RETURN)

    def send_request(self, search_params: SearchParams) -> ResponseOutput:
        """Visit a URL with selenium and save HTML response"""

        response_output = ResponseOutput(
            url=search_params.url,
            user_agent=self.browser_info.get("user_agent", ""),
            timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat(),
        )

        pre_nav_url: str | None = None
        try:
            driver = self._require_driver()
            pre_nav_url = driver.current_url
            driver.get(search_params.url)
            time.sleep(2)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "search")))
            time.sleep(2)
            response_output.html = driver.page_source
            response_output.url = driver.current_url
            response_output.response_code = 200

            # Expand AI overview if requested
            if search_params.ai_expand:
                expanded_html = self.expand_ai_overview()
                if expanded_html:
                    len_diff = len(expanded_html) - len(response_output.html)
                    self.log.debug(f"SERP | expanded html | len diff: {len_diff}")
                    response_output.html = expanded_html

        except Exception as e:
            self.log.exception(f"SERP | Chromedriver error | {str(e)}")
            # Capture the live URL and whatever HTML rendered anyway -- a
            # CAPTCHA challenge redirects to /sorry/ and never shows #search,
            # so the redirect would otherwise be discarded with the timeout.
            # Only when the URL moved off the pre-navigation page: a failure
            # before navigation would otherwise record the previous query's SERP.
            if self.driver is not None and pre_nav_url is not None:
                try:
                    live_url = self.driver.current_url
                    if live_url and live_url != pre_nav_url:
                        response_output.url = live_url
                        response_output.html = self.driver.page_source
                except Exception:
                    pass
        finally:
            self.delete_cookies()

        return response_output

    def expand_ai_overview(self):
        """Expand AI overview box by clicking it"""
        driver = self._require_driver()
        show_more_button_xpath = "//div[@jsname='rPRdsc' and @role='button']"
        show_all_button_xpath = '//div[contains(@class, "trEk7e") and @role="button"]'

        try:
            driver.find_element(By.XPATH, show_more_button_xpath)
            show_more_button_exists = True
        except NoSuchElementException:
            show_more_button_exists = False

        if show_more_button_exists:
            try:
                show_more_button = WebDriverWait(driver, 1).until(
                    EC.element_to_be_clickable((By.XPATH, show_more_button_xpath))
                )
                if show_more_button is not None:
                    show_more_button.click()
                    try:
                        time.sleep(2)  # Wait for additional content to load
                        show_all_button = WebDriverWait(driver, 1).until(
                            EC.element_to_be_clickable((By.XPATH, show_all_button_xpath))
                        )
                        show_all_button.click()
                    except Exception:
                        pass

                    # Return expanded content
                    return driver.page_source

            except Exception:
                pass

        return None

    def cleanup(self) -> bool:
        """Quit the browser, returning True on success or if there's nothing to do.

        ``driver.quit()`` already closes every window and ends the session, so no
        per-window/cookie teardown is needed. During interpreter shutdown the
        chromedriver session is often already gone, which makes quit() emit noisy
        urllib3 connection-refused retries; mute that logger for the duration.
        """
        if not self.driver:
            return True

        pool_logger = logging.getLogger("urllib3.connectionpool")
        prev_level = pool_logger.level
        pool_logger.setLevel(logging.ERROR)
        try:
            self.driver.quit()
            self.log.debug("Browser successfully closed")
            return True
        except Exception as e:
            self.log.debug(f"Browser already closed or unreachable: {e}")
            return False
        finally:
            pool_logger.setLevel(prev_level)
            self.driver = None

    def delete_cookies(self):
        """Delete all cookies from the browser"""
        if self.driver:
            try:
                self.driver.delete_all_cookies()
            except Exception as e:
                self.log.debug(f"Failed to delete cookies: {str(e)}")

    def __del__(self):
        """Destructor to ensure browser is closed when object is garbage collected"""
        try:
            self.cleanup()
        except Exception:
            pass
