from . import parsers
from . import locations
from . import webutils as wu
from . import utils
from . import logger
from .models.configs import LogConfig, SeleniumConfig, RequestsConfig, SearchConfig, SearchMethod
from .models.data import BaseSERP

import os
import time
import json
import brotli
import requests
import pandas as pd
from typing import Any, Dict, Optional, Union
from datetime import datetime, timezone

# selenium updates
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from importlib import metadata
WS_VERSION = metadata.version('WebSearcher')

class SearchEngine:
    """Collect Search Engine Results Pages (SERPs)"""
    def __init__(self, 
            method: Union[str, SearchMethod] = SearchMethod.SELENIUM,
            base_config: Union[dict, LogConfig] = {},
            selenium_config: Union[dict, SeleniumConfig] = {},
            requests_config: Union[dict, RequestsConfig] = {}
        ) -> None:
        """Initialize the search engine

        Args: 
            method (Union[str, SearchMethod], optional): The method to use for searching, either 'requests' or 'selenium'. Defaults to SearchMethod.SELENIUM.
            base_config (Union[dict, LogConfig], optional): Common search configuration. Defaults to None.
            selenium_config (Union[dict, SeleniumConfig], optional): Selenium-specific configuration. Defaults to None.
            requests_config (Union[dict, RequestsConfig], optional): Requests-specific configuration. Defaults to None.
        """

        # Initialize configuration
        self.version = WS_VERSION
        self.config = SearchConfig.create({
            "method": SearchMethod.create(method),
            "base": LogConfig.create(base_config),
            "selenium": SeleniumConfig.create(selenium_config),
            "requests": RequestsConfig.create(requests_config),
        })

        # Initialize common attributes
        self.version: str = WS_VERSION
        self.base_url: str = 'https://www.google.com/search'
        self.params: Dict[str, Any] = {}

        # Initialize method-specific attributes
        if self.config.method == SearchMethod.SELENIUM:
            self.driver = None
        else:
            self.config.requests.sesh = self.config.requests.sesh or wu.start_sesh(headers=self.config.requests.headers)

        # Initialize search details
        self.qry: str = None
        self.loc: str = None
        self.lang: str = None
        self.num_results = None
        self.url: str = None
        self.timestamp: str = None
        self.serp_id: str = None
        self.crawl_id: str = None

        # Initialize search outputs
        self.response = None  # type: Optional[requests.Response]
        self.html: str = None
        self.results: list = []
        self.serp_features: dict = {}
        self.serp: dict = {}

        # Set a log file, prints to console by default
        self.log = logger.Logger(
            console=True if not self.config.base.log_fp else False,
            console_level=self.config.base.log_level,
            file_name=self.config.base.log_fp, 
            file_mode=self.config.base.log_mode,
            file_level=self.config.base.log_level,
        ).start(__name__)

    def search(self, 
            qry: str, 
            location: str = None, 
            lang: str = None, 
            num_results: int = None, 
            ai_expand: bool = False,
            serp_id: str = '', 
            crawl_id: str = ''
        ):
        """Conduct a search and save HTML
        
        Args:
            qry (str): The search query
            location (str, optional): A location's Canonical Name
            num_results (int, optional): The number of results to return
            ai_expand: (bool, optional): Whether to use selenium to expand AI overviews
            serp_id (str, optional): A unique identifier for this SERP
            crawl_id (str, optional): An identifier for this crawl
        """

        self._prepare_search(qry=qry, location=location, lang=lang, num_results=num_results)
        self._conduct_search(serp_id=serp_id, crawl_id=crawl_id, ai_expand=ai_expand)

    def _prepare_search(self, qry: str, location: str = None, lang: str = None, num_results: int = None):
        """Prepare a search URL and metadata for the given query and location"""
        self.qry = str(qry)
        self.loc = str(location) if not pd.isnull(location) else ''
        self.lang = str(lang) if not pd.isnull(lang) else ''
        self.num_results = num_results
        self.params = {}
        self.params['q'] = wu.encode_param_value(self.qry)
        if self.num_results:
            self.params['num'] = self.num_results
        if self.lang and self.lang not in {'None', 'nan'}:
            self.params['hl'] = self.lang
        if self.loc and self.loc not in {'None', 'nan'}:
            self.params['uule'] = locations.convert_canonical_name_to_uule(self.loc)
        self.url = f"{self.base_url}?{wu.join_url_quote(self.params)}"

    def _conduct_search(self, serp_id:str = '', crawl_id:str = '', ai_expand:bool = False):
        if self.config.method == SearchMethod.SELENIUM:
            self._conduct_search_chromedriver(serp_id=serp_id, crawl_id=crawl_id, ai_expand=ai_expand)
        elif self.config.method == SearchMethod.REQUESTS:
            self._conduct_search_requests(serp_id=serp_id, crawl_id=crawl_id)

    # ==========================================================================
    # Selenium method

    def _init_chromedriver(self) -> None:
        """Initialize Chrome driver with selenium-specific config"""
        self.log.debug(f'SERP | init uc chromedriver | kwargs: {self.config.selenium.__dict__}')
        self.driver = uc.Chrome(**self.config.selenium.__dict__)
        self.user_agent = self.driver.execute_script('return navigator.userAgent')
        self.response_code = None
        
        # Log version information
        self.browser_info = {
            'browser_id': "",
            'browser_name': self.driver.capabilities['browserName'],
            'browser_version': self.driver.capabilities['browserVersion'],
            'driver_version': self.driver.capabilities['chrome']['chromedriverVersion'].split(' ')[0],
        }
        self.browser_info['browser_id'] = utils.hash_id(json.dumps(self.browser_info))
        self.log.debug(json.dumps(self.browser_info, indent=4))

    def _send_chromedriver_typed_query(self):
        """Send a typed query to the search box"""
        time.sleep(2)
        self.driver.get('https://www.google.com')
        time.sleep(2)
        search_box = self.driver.find_element(By.ID, "APjFqb")
        search_box.clear()
        search_box.send_keys(self.qry)
        search_box.send_keys(Keys.RETURN)

    def _send_chromedriver_request(self):
        """Use a prepared URL to conduct a search"""

        time.sleep(2)
        self.driver.get(self.url)
        time.sleep(2)
        
        # wait for the page to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "search")) 
        )
        time.sleep(2) #including a sleep to allow the page to fully load

        self.html = self.driver.page_source
        self.url = self.driver.current_url
        self.response_code = 0
        log_msg = f"{self.response_code} | {self.qry}"
        log_msg = f"{log_msg} | {self.loc}" if self.loc else log_msg
        self.log.info(log_msg)

    def _conduct_search_chromedriver(self, serp_id: str = '', crawl_id: str = '', ai_expand = False):
        """Send a search request and handle errors"""
        if not self.driver:
            self._init_chromedriver()

        self.timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        self.serp_id = serp_id if serp_id else utils.hash_id(self.qry + self.loc + self.timestamp)
        self.crawl_id = crawl_id
        try:
            self._send_chromedriver_request()
            self.html = self.driver.page_source
        except Exception as e:
            self.log.exception(f'SERP | Chromedriver error | {self.serp_id}: {str(e)}')

        if ai_expand:
            self._expand_ai_overview()
        
        # Only delete cookies, don't close the driver here
        # The driver will be closed when cleanup() is called
        if self.driver:
            try:
                self.driver.delete_all_cookies()
            except Exception as e:
                self.log.warning(f"Failed to delete cookies: {str(e)}")

    def _expand_ai_overview(self):
        """Expand AI overview box by clicking it"""
        show_more_button_xpath = "//div[@jsname='rPRdsc' and @role='button']"
        show_all_button_xpath = '//div[contains(@class, "trEk7e") and @role="button"]'

        try:
            self.driver.find_element(By.XPATH, show_more_button_xpath)
            show_more_button_exists = True
        except NoSuchElementException:
            show_more_button_exists = False
        
        if show_more_button_exists:
            try:
                show_more_button = WebDriverWait(self.driver, 1).until(
                    EC.element_to_be_clickable((By.XPATH, show_more_button_xpath))
                )
                if show_more_button is not None:
                    show_more_button.click()
                    try:
                        time.sleep(2) # Wait for additional content to load
                        show_all_button = WebDriverWait(self.driver, 1).until(
                            EC.element_to_be_clickable((By.XPATH, show_all_button_xpath))
                        )
                        show_all_button.click()
                    except Exception:
                        pass
                    
                     # Overwrite html with expanded content
                    new_html = self.driver.page_source
                    self.log.debug(f'SERP | overwriting expanded content | len diff: {len(new_html) - len(self.html)}')
                    self.html = new_html

            except Exception:
                pass

    def cleanup(self):
        """Clean up resources, particularly Selenium's browser instance
        
        Returns:
            bool: True if cleanup was successful or not needed, False if cleanup failed
        """
        if self.config.method == SearchMethod.SELENIUM and hasattr(self, 'driver') and self.driver:
            try:
                # Try a more thorough cleanup
                try:
                    self.driver.delete_all_cookies()
                except Exception:
                    pass
                
                try:
                    # Close all tabs/windows
                    original_handle = self.driver.current_window_handle
                    for handle in self.driver.window_handles:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                except Exception:
                    pass
                
                # Finally quit the driver
                self.driver.quit()
                self.driver = None
                self.log.debug(f'Browser successfully closed')
                return True
            except Exception as e:
                self.log.warning(f'Failed to close browser: {e}')
                # Force driver to be None so we create a fresh instance next time
                self.driver = None
                return False
        return True
    
    def __del__(self):
        """Destructor to ensure browser is closed when object is garbage collected"""
        try:
            self.cleanup()
        except Exception:
            pass

    # ==========================================================================
    # Requests method

    def _conduct_search_requests(self, serp_id: str = '', crawl_id: str = ''):
        """Send a search request and handle errors"""

        self.timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        self.serp_id = serp_id if serp_id else utils.hash_id(self.qry + self.loc + self.timestamp)
        self.crawl_id = crawl_id
        self.user_agent = self.config.requests.headers['User-Agent']

        try:
            self._send_request()
        except requests.exceptions.ConnectionError:
            self.log.exception(f'SERP | Connection error | {self.serp_id}')
            self._reset_ssh_tunnel()
        except requests.exceptions.Timeout:
            self.log.exception(f'SERP | Timeout error | {self.serp_id}')
        except Exception:
            self.log.exception(f'SERP | Unknown error | {self.serp_id}')
        finally:
            self._handle_response()

    def _send_request(self):
        self.response = self.config.requests.sesh.get(self.url, timeout=10)
        self.response_code = self.response.status_code
        log_msg = f"{self.response_code} | {self.qry}"
        log_msg = f"{log_msg} | {self.loc}" if self.loc else log_msg
        self.log.info(log_msg)

    def _reset_ssh_tunnel(self):
        if self.config.requests.ssh_tunnel:
            self.config.requests.ssh_tunnel.tunnel.kill()
            self.config.requests.ssh_tunnel.open_tunnel()
            self.log.info(f'SERP | Restarted SSH tunnel | {self.serp_id}')
            time.sleep(10) # Allow time to establish connection

    def _handle_response(self):
        try:
            if self.config.requests.unzip:  
                self._unzip_html()
            else:
                self.html = self.response.content
            self.html = self.html.decode('utf-8', 'ignore')
        except Exception:
            self.log.exception(f'Response handling error')

    def _unzip_html(self) -> None:
        """Unzip brotli zipped html 

        Can allow zipped responses by setting the header `"Accept-Encoding"`.
        Zipped reponses are the default because it is more efficient.
        """

        rcontent = self.response.content
        try:
            self.html = brotli.decompress(rcontent)
        except brotli.error:
            self.html = rcontent
        except Exception:
            self.log.exception(f'unzip error | serp_id : {self.serp_id}')
            self.html = rcontent

    # ==========================================================================
    # Parsing

    def parse_all(self):
        """Parse results and extract SERP features in a single pass"""
        assert self.html, "No HTML found"
        try:
            # Use the enhanced parse_serp function to get both results and features in one pass
            self.results, self.serp_features = parsers.parse_serp(self.html, extract_features=True)
        except Exception:
            self.log.exception(f'Combined parsing error | serp_id : {self.serp_id}')

    def parse_results(self):
        """Parse a SERP - see parsers.py"""
        assert self.html, "No HTML found"
        try:
            self.results = parsers.parse_serp(self.html)
        except Exception:
            self.log.exception(f'Parsing error | serp_id : {self.serp_id}')

    def parse_serp_features(self):
        """Extract SERP features - see parsers.py"""
        assert self.html, "No HTML found"
        try:
            self.serp_features = parsers.FeatureExtractor.extract_features(self.html)
        except Exception:
            self.log.exception(f'Feature extraction error | serp_id : {self.serp_id}')

    # ==========================================================================
    # Saving

    def prepare_serp_save(self):
        self.serp = BaseSERP(
            qry=self.qry, 
            loc=self.loc, 
            lang=self.lang,
            url=self.url, 
            html=self.html,
            response_code=self.response_code,
            user_agent=self.user_agent,
            timestamp=self.timestamp,
            serp_id=self.serp_id,
            crawl_id=self.crawl_id,
            version=self.version,
            method=self.config.method.value
        ).model_dump()

    def save_serp(self, save_dir: str = "", append_to: str = ""):
        """Save SERP to file

        Args:
            save_dir (str, optional): Save results as `save_dir/{serp_id}.html`
            append_to (str, optional): Append results to this file path
        """
        assert self.html, "No HTML found"
        assert save_dir or append_to, "Must provide a save_dir or append_to file path"

        if append_to:
            self.prepare_serp_save()
            utils.write_lines([self.serp], append_to)

        else:
            fp = os.path.join(save_dir, f'{self.serp_id}.html')
            with open(fp, 'w') as outfile:
                outfile.write(self.html)

    def save_search(self, append_to: str = ""):
        """Save search metadata (excludes HTML) to file

        Args:
            append_to (str, optional): Append results to this file path
        """
        assert self.html, "No HTML found"
        assert append_to, "Must provide an append_to file path"

        if not self.serp:
            self.prepare_serp_save()
        
        if not self.serp_features:
            self.parse_serp_features()
        
        self.serp_metadata = {k: v for k, v in self.serp.items() if k != 'html'}
        self.serp_metadata.update(self.serp_features)
        utils.write_lines([self.serp_metadata], append_to)

    def save_results(self, save_dir: str = "", append_to: str = ""):
        """Save parsed results
        
        Args:
            save_dir (str, optional): Save results as `save_dir/results/{serp_id}.json`
            append_to (bool, optional): Append results to this file path
        """
        assert save_dir or append_to, "Must provide a save_dir or append_to file path"

        if self.results:
            if append_to:
                result_metadata = {'crawl_id': self.crawl_id, 'serp_id': self.serp_id, 'version': self.version}
                results_output = [{**result, **result_metadata} for result in self.results]
                utils.write_lines(results_output, append_to)
            else:
                fp = os.path.join(save_dir, 'results', f'{self.serp_id}.json')
                utils.write_lines(self.results, fp)
        else:
            self.log.info(f'No parsed results for serp_id: {self.serp_id}')

