from . import parsers
from . import locations
from . import webutils as wu
from . import utils
from . import logger
from .models import BaseSERP

import os
import time
import brotli
import requests
import subprocess
import pandas as pd
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# selenium updates
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from importlib import metadata
WS_VERSION = metadata.version('WebSearcher')

# Default headers to send with requests (i.e. device fingerprint)
DEFAULT_HEADERS = {
   'Host': 'www.google.com',
   'Referer': 'https://www.google.com/',
   'Accept': '*/*',
   'Accept-Encoding': 'gzip,deflate,br',
   'Accept-Language': 'en-US,en;q=0.5',
   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0',
}

class SearchEngine:
    """Collect Search Engine Results Pages (SERPs)"""
    def __init__(self, 
            headers: Dict[str, str] = None,
            sesh: Optional[requests.Session] = None, 
            ssh_tunnel: Optional[subprocess.Popen] = None, 
            unzip: bool = True,
            log_fp: str = '', 
            log_mode: str = 'a+',
            log_level: str ='INFO',
        ) -> None:
        """Initialize a `requests.Session` to conduct searches through or
        pass an existing one with an optional SSH tunnel.
        
        Args:
            headers (dict, optional): Headers to send with requests.
            unzip (bool, optional): Unzip brotli zipped html responses.
            sesh (None, optional): A `requests.Session` object.
            ssh_tunnel (None, optional): An SSH tunnel subprocess from `webutils`.
            log_fp (str, optional): A file to log function process output to.
            log_mode (str, optional): Write over the log file or append to it.
            log_level (str, optional): The file logging level.
        """

        # Initialize data storage
        self.version: str = WS_VERSION
        self.base_url: str = 'https://www.google.com/search'
        self.headers: Dict[str, str] = headers or DEFAULT_HEADERS
        self.sesh: requests.Session = sesh or wu.start_sesh(headers=self.headers)
        self.ssh_tunnel: subprocess.Popen = ssh_tunnel
        self.unzip: bool = unzip
        self.params: Dict[str, Any] = {}

        # Initialize search details
        self.qry: str = None
        self.loc: str = None
        self.lang: str = None
        self.num_results = None
        self.url: str = None
        self.timestamp: str = None
        self.serp_id: str = None
        self.crawl_id: str = None
        self.response: requests.Response = None
        self.html: str = None
        self.results: list = []
        self.serp_features: dict = {}
        self.serp: dict = {}

        # Set a log file, prints to console by default
        self.log = logger.Logger(
            console=True if not log_fp else False,
            console_level=log_level,
            file_name=log_fp, 
            file_mode=log_mode,
            file_level=log_level,
        ).start(__name__)

    def search(self, 
            qry: str, 
            location: str = None, 
            lang: str = None, 
            num_results: int = None, 
            method: str = 'selenium',
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

        if method == 'selenium':
            self._conduct_chromedriver_search(serp_id=serp_id, crawl_id=crawl_id, ai_expand=ai_expand)
        elif method == 'requests':
            self._conduct_search(serp_id=serp_id, crawl_id=crawl_id)
            self._handle_response()

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

    def launch_chromedriver(
            self, 
            headless: bool = False, 
            version_main: int = 133,
            use_subprocess: bool = False, 
            chromedriver_path: str = ''
        ) -> None:
        self.headless = headless
        self.use_subprocess = use_subprocess
        self.chromedriver_path = chromedriver_path
        self.version_main = version_main
        self._init_chromedriver()

    def _init_chromedriver(self):
        self.log.info(f'SERP | Launching ChromeDriver | headless: {self.headless} | subprocess: {self.use_subprocess} | version: {self.version_main}')
        if self.chromedriver_path == '':
            self.driver = uc.Chrome(headless = self.headless, subprocess = self.use_subprocess, version_main = self.version_main)
        else:
            self.driver = uc.Chrome(headless = self.headless, subprocess = self.use_subprocess, chromedriver_path = self.chromedriver_path, version_main = self.version_main)
        time.sleep(2)
        self.driver.get('https://www.google.com')
        time.sleep(2)

    def _send_chromedriver_request(self):
        search_box = self.driver.find_element(By.ID, "APjFqb")
        search_box.clear()
        search_box.send_keys(self.qry)
        search_box.send_keys(Keys.RETURN)
        
        # wait for the page to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "search")) 
        )
        time.sleep(2) #including a sleep to allow the page to fully load
        self.html = self.driver.page_source
        self.url = self.driver.current_url

    def _send_request(self):
        self.url = f"{self.base_url}?{wu.join_url_quote(self.params)}"
        self.response = self.sesh.get(self.url, timeout=10)
        log_msg = f"{self.response.status_code} | {self.qry}"
        log_msg = f"{log_msg} | {self.loc}" if self.loc else log_msg
        self.log.info(log_msg)

    def _conduct_chromedriver_search(self, serp_id: str = '', crawl_id: str = '', ai_expand = False):
        """Send a search request and handle errors"""
        self.timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        self.serp_id = serp_id if serp_id else utils.hash_id(self.qry + self.loc + self.timestamp)
        self.crawl_id = crawl_id
        try:
            self._send_chromedriver_request()
            self.html = self.driver.page_source
        except:
            self.log.exception(f'SERP | Chromedriver error | {self.serp_id}')

        if ai_expand:
            self._expand_ai_overview()           # Expand AI overview box by clicking it
        self.driver.delete_all_cookies()

    def _expand_ai_overview(self):
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
                    self.html = self.driver.page_source

            except Exception:
                pass

    def _reset_ssh_tunnel(self):
        if self.ssh_tunnel:
            self.ssh_tunnel.tunnel.kill()
            self.ssh_tunnel.open_tunnel()
            self.log.info(f'SERP | Restarted SSH tunnel | {self.serp_id}')
            time.sleep(10) # Allow time to establish connection

    def _handle_response(self):
        try:
            if self.unzip:  
                self._unzip_html()
            else:
                self.html = self.response.content
            self.html = self.html.decode('utf-8', 'ignore')
        except Exception:
            self.log.exception(f'Response handling error')

    def _unzip_html(self):
        """Unzip brotli zipped html 

        Can allow zipped responses by setting the header `"Accept-Encoding"`.
        Zipped reponses are the default because it is more efficient.
        
        Returns:
            str: Decompressed html
        """

        rcontent = self.response.content
        try:
            self.html = brotli.decompress(rcontent)
        except brotli.error:
            self.html = rcontent
        except Exception:
            self.log.exception(f'unzip error | serp_id : {self.serp_id}')
            self.html = rcontent

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

    def prepare_serp_save(self):
        self.serp = BaseSERP(
            qry=self.qry, 
            loc=self.loc, 
            lang=self.lang,
            url=self.url, 
            html=self.html,
            response_code=0 if not self.response else self.response.status_code,
            user_agent='' if not self.response else self.headers['User-Agent'],
            timestamp=self.timestamp,
            serp_id=self.serp_id,
            crawl_id=self.crawl_id,
            version=self.version,
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


