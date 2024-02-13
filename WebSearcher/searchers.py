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
import pkg_resources
from datetime import datetime
from typing import Any, Dict, Optional

# Current version
WS_VERSION = pkg_resources.get_distribution('WebSearcher').version

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

        # Initialize search data
        self.qry: str = None
        self.loc: str = None
        self.url: str = None
        self.timestamp: str = None
        self.serp_id: str = None
        self.crawl_id: str = None
        self.response: requests.Response = None
        self.html: str = None
        self.results: list = []
        
        # Set a log file, prints to console by default
        self.log = logger.Logger(
            console=True if not log_fp else False,
            console_level=log_level,
            file_name=log_fp, 
            file_mode=log_mode,
            file_level=log_level,
        ).start(__name__)


    def search(self, qry: str, location: str = '', serp_id: str = '', crawl_id: str = ''):
        """Conduct a search and save HTML
        
        Args:
            qry (str): The search query
            location (str, optional): A location's Canonical Name.
            serp_id (str, optional): A unique identifier for this SERP
            crawl_id (str, optional): An identifier for this crawl
        """
        self.prepare_search(qry, location)
        self.conduct_search(serp_id, crawl_id)
        self.handle_response()


    def prepare_search(self, qry: str, location: str = ''):
        """Prepare a search URL and metadata for the given query and location"""
        self.qry = str(qry)
        self.loc = str(location)
        self.params = {}
        self.params['q'] = wu.encode_param_value(self.qry)
        if location:
            self.params['uule'] = locations.get_location_id(canonical_name=self.loc)


    def conduct_search(self, serp_id: str = '', crawl_id: str = ''):
        """Send a search request and handle errors"""

        self.timestamp = datetime.utcnow().isoformat()
        self.serp_id = serp_id if serp_id else utils.hash_id(self.qry + self.loc + self.timestamp)
        self.crawl_id = crawl_id
        try:
            self.send_request()
        except requests.exceptions.ConnectionError:
            self.log.exception(f'SERP | Connection error | {self.serp_id}')
            self.reset_ssh_tunnel()
        except requests.exceptions.Timeout:
            self.log.exception(f'SERP | Timeout error | {self.serp_id}')
        except Exception:
            self.log.exception(f'SERP | Unknown error | {self.serp_id}')


    def send_request(self):
        self.url = f"{self.base_url}?{wu.join_url_quote(self.params)}"
        self.response = self.sesh.get(self.url, timeout=10)
        log_msg = f"{self.response.status_code} | {self.qry}"
        log_msg = f"{log_msg} | {self.loc}" if self.loc else log_msg
        self.log.info(log_msg)


    def reset_ssh_tunnel(self):
        if self.ssh_tunnel:
            self.ssh_tunnel.tunnel.kill()
            self.ssh_tunnel.open_tunnel()
            self.log.info(f'SERP | Restarted SSH tunnel | {self.serp_id}')
            time.sleep(10) # Allow time to establish connection


    def handle_response(self):
        try:
            # Unzip string if True
            if self.unzip:  
                self.unzip_html()
            else:
                # Get response string
                self.html = self.response.content

            # Decode string
            self.html = self.html.decode('utf-8', 'ignore')
        
        except Exception:
            self.log.exception(f'Response handling error')


    def unzip_html(self):
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
            self.results = parsers.parse_serp(self.html, serp_id=self.serp_id, make_soup=True)
        except Exception:
            self.log.exception(f'Parsing error | serp_id : {self.serp_id}')


    def save_serp(self, save_dir: str = '', append_to: str = ""):
        """Save SERP to file

        Args:
            save_dir (str, optional): Save results as `save_dir/{serp_id}.html`
            append_to (str, optional): Append results to this file path
        """
        assert self.html, "No HTML found"
        assert save_dir or append_to, "Must provide a save_dir or append_to file path"

        if append_to:
            # Prepare and save SERP row
            serp = BaseSERP(
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
            )
            utils.write_lines([serp.model_dump()], append_to)

        else:
            fp = os.path.join(save_dir, f'{self.serp_id}.html')
            with open(fp, 'w') as outfile:
                outfile.write(self.html)


    def save_results(self, save_dir: str = '', append_to: str = ""):
        """Save parsed results
        
        Args:
            save_dir (str, optional): Save results as `save_dir/results/{serp_id}.json`
            append_to (bool, optional): Append results to this file path
        """        
        assert save_dir or append_to, "Must provide a save_dir or append_to file path"

        if self.results:
            if append_to:
                utils.write_lines(self.results, append_to)
            else:
                fp = os.path.join(save_dir, 'results', f'{self.serp_id}.json')
                utils.write_lines(self.results, fp)
        else:
            self.log.info(f'No parsed results for serp_id: {self.serp_id}')
