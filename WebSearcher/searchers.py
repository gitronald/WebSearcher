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
from datetime import datetime, timezone
from typing import Any, Dict, Optional

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
            headers: Dict[str, str] = DEFAULT_HEADERS,
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
        self.headers: Dict[str, str] = headers
        self.sesh: requests.Session = sesh if sesh else wu.start_sesh(headers=self.headers)
        self.ssh_tunnel: subprocess.Popen = ssh_tunnel
        self.unzip: bool = unzip
        self.params: Dict[str, Any] = {}

        # Initialize search details
        self.qry: str = None
        self.loc: str = None
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


    def search(self, qry: str, location: str = None, num_results: int = None, serp_id: str = '', crawl_id: str = ''):
        """Conduct a search and save HTML
        
        Args:
            qry (str): The search query
            location (str, optional): A location's Canonical Name.
            num_results (int, optional): The number of results to return.
            serp_id (str, optional): A unique identifier for this SERP
            crawl_id (str, optional): An identifier for this crawl
        """
        self._prepare_search(qry=qry, location=location, num_results=num_results)
        self._conduct_search(serp_id=serp_id, crawl_id=crawl_id)
        self._handle_response()


    def _prepare_search(self, qry: str, location: str = None, num_results: int = None):
        """Prepare a search URL and metadata for the given query and location"""
        self.qry = str(qry)
        self.loc = str(location) if location else ''
        self.num_results = num_results
        self.params = {}
        self.params['q'] = wu.encode_param_value(self.qry)
        if self.num_results:
            self.params['num'] = self.num_results
        if self.loc and self.loc != 'None':
            self.params['uule'] = locations.get_location_id(canonical_name=self.loc)


    def _conduct_search(self, serp_id: str = '', crawl_id: str = ''):
        """Send a search request and handle errors"""

        self.timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        self.serp_id = serp_id if serp_id else utils.hash_id(self.qry + self.loc + self.timestamp)
        self.crawl_id = crawl_id
        try:
            self._send_request()
        except requests.exceptions.ConnectionError:
            self.log.exception(f'SERP | Connection error | {self.serp_id}')
            self._reset_ssh_tunnel()
        except requests.exceptions.Timeout:
            self.log.exception(f'SERP | Timeout error | {self.serp_id}')
        except Exception:
            self.log.exception(f'SERP | Unknown error | {self.serp_id}')


    def _send_request(self):
        self.url = f"{self.base_url}?{wu.join_url_quote(self.params)}"
        self.response = self.sesh.get(self.url, timeout=10)
        log_msg = f"{self.response.status_code} | {self.qry}"
        log_msg = f"{log_msg} | {self.loc}" if self.loc else log_msg
        self.log.info(log_msg)


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
            url=self.url, 
            html=self.html,
            response_code=self.response.status_code,
            user_agent=self.headers['User-Agent'],
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
