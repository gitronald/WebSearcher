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
from datetime import datetime
from typing import Any, Dict, Optional

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
            unzip: bool = True,
            sesh: Optional[requests.Session] = None, 
            ssh_tunnel: Optional[subprocess.Popen] = None, 
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

        self.base_url = 'https://www.google.com/search'
        self.params = {}
        self.headers = headers
        self.unzip = unzip

        # Set a log file, prints to console by default
        self.log = logger.Logger(
            console=True if not log_fp else False,
            console_level=log_level,
            file_name=log_fp, 
            file_mode=log_mode,
            file_level=log_level,
        ).start(__name__)

        # Set a requests session
        self.sesh = sesh if sesh else wu.start_sesh(headers=self.headers)

        # Set an SSH tunnel - conducting the search from somewhere else
        self.ssh_tunnel = ssh_tunnel

        # Initialize data storage
        self.html = None
        self.results = []


    def set_location(self, canonical_name: str = ''):
        """Set location using uule parameter derived from location name.

        Location provided must be a "Canonical Name."
        See download_locations.py or ws.download_locations() to 
        download a csv of locations and their canonical names. 

        Credit for figuring this out goes to the author of the PHP version: 
        https://github.com/512banque/uule-grabber/blob/master/uule.php      

        """
        if canonical_name:
            self.loc = canonical_name
            self.params['uule'] = locations.get_location_id(canonical_name)


    def prepare_url(self, qry, location):
        """Prepare a query

        Set as original query and current query per default behavior in desktop 
        search
        
        Args:
            qry (str): Search query
            location (str): location name
        """
        self.qry = str(qry)
        self.loc = str(location)
        self.params['q'] = wu.encode_param_value(qry)

        # Reset previous location
        if 'uule' in self.params:
            self.params.pop('uule')
        if location:
            self.set_location(location)


    def snapshot(self):
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
        self.log.info(f'{self.response.status_code} | {self.qry} | {self.loc if self.loc else self.qry}')


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
        Zipped reponses are the default because it is more efficient for them
        
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


    def search(self, qry, location='', serp_id='', crawl_id=''):
        """Conduct a search and save HTML
        
        Args:
            qry (str): The search query
            location (str, optional): A location's Canonical Name.
            serp_id (str, optional): A unique identifier for this SERP
        """
        self.prepare_url(qry, location=location)
        self.timestamp = datetime.utcnow().isoformat()
        self.serp_id = serp_id if serp_id else utils.hash_id(qry + location + self.timestamp)
        self.crawl_id = crawl_id
        self.snapshot()
        self.handle_response()


    def save_serp(self, save_dir='.', append_to=''):
        """Save SERP to file

        Args:
            save_dir (str, optional): Save results as `save_dir/{serp_id}.html`
            append_to (str, optional): Append results to this file path
        """
        assert self.html, "Must conduct a search first"

        if append_to:
            # Keep a selection of object keys
            keep_keys = [
                'qry',
                'loc',
                'url',
                'html',
                'headers',
                'timestamp',
                'serp_id',
                'crawl_id',
            ]
            all_items = dict(vars(self).items())
            out_data = {k: all_items[k] for k in keep_keys}
            out_data['response_code'] = self.response.status_code
            self.log.debug(f"Validating SERP data")
            serp = BaseSERP(**out_data)
            output = [serp.model_dump()]
            utils.write_lines(output, append_to)

        else:
            fn = f'{self.serp_id}.html'
            fp = os.path.join(save_dir, fn)
            self.log.debug(f"saving: {fp}")
            with open(fp, 'w') as outfile:
                outfile.write(self.html)


    def parse_results(self):
        """Parse a SERP - see parsers.py"""

        assert self.html, "No HTML found"
        try:
            soup = wu.make_soup(self.html)
            self.results = parsers.parse_serp(soup, serp_id=self.serp_id)

        except Exception:
            self.log.exception(f'Parsing error | serp_id : {self.serp_id}')


    def save_results(self, save_dir='.', append_to=False):
        """Save parsed results
        
        Args:
            save_dir (str, optional): Save results as `save_dir/results/{serp_id}.json`
            append_to (bool, optional): Append results to this file path
        """
        # Save parsed results
        if self.results:
            if append_to:
                utils.write_lines(self.results, append_to)
            else:
                fp = os.path.join(save_dir, 'results', f'{self.serp_id}.json')
                utils.write_lines(self.results, fp)
        else:
            self.log.info(f'No parsed results for serp_id {self.serp_id}')
