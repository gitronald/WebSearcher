from . import parsers
from . import locations
from . import webutils as wu
from . import utils
from . import logger

import os
import json
import time
import brotli
import requests
from hashlib import sha224
from datetime import datetime

# Default headers to send with requests (i.e. device fingerprint)
DEFAULT_HEADERS = {
    'Host': 'www.google.com',
    'Referer': 'https://www.google.com/',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip,deflate,br',
    'Accept-Language': 'en-US,en;q=0.5',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0',
}

def utc_stamp(): return datetime.utcnow().isoformat()
def generate_rand_id(): return sha224(utc_stamp().encode('utf-8')).hexdigest()
def hash_id(s): return sha224(s.encode('utf-8')).hexdigest()

class SearchEngine(object):
    """ Collect Search Engine Results Pages (SERPs)
    
    Location provided must be a "Canonical Name"

    """
    def __init__(self, 
        sesh=None, ssh_tunnel=None, 
        log_fp='', log_mode='a+',
        headers=DEFAULT_HEADERS,
        unzip=True):
        """Initialize a `requests.Session` to conduct searches through or
        pass an existing one with an optional SSH tunnel.
        
        Args:
            sesh (None, optional): A `requests.Session` object.
            ssh_tunnel (None, optional): An SSH tunnel subprocess from `webutils`.
            log_fp (str, optional): A file to log function process output to.
            log_mode (str, optional): Write over the log file or append to it.
            headers (dict, optional): Headers to send with requests.
            unzip (bool, optional): Unzip brotli zipped html responses.
        """

        self.base_url = 'https://www.google.com/search'
        self.params = {}
        self.headers = headers

        # Set a requests session
        self.sesh = sesh if sesh else wu.start_sesh(headers=self.headers)

        # Set a log file, prints to console by default
        self.log = logger.Logger(
            file_name=log_fp, 
            file_mode=log_mode
        ).start(__name__)

        # Set an SSH tunnel - conducting the search from somewhere else
        self.ssh_tunnel = ssh_tunnel

        # Initialize data storage - search results
        self.html = None
        self.unzip = unzip
        self.results = []


    def set_location(self, canonical_name):
        """Set location using uule parameter derived from location name

        Credit for figuring this out goes to the author of the PHP version: 
        https://github.com/512banque/uule-grabber/blob/master/uule.php.

        See download_locations.py or ws.download_locations() to 
        download a csv of locations and their canonical names. 

        """
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
        
        self.params['q'] = '+'.join(self.qry.split(' '))

        # Reset previous location
        if 'uule' in self.params:
            self.params.pop('uule')
        if location:
            self.set_location(location)

        # Create request URL
        param_str = wu.join_url_quote(self.params)
        self.url = f'{self.base_url}?{param_str}'


    def snapshot(self):
        try:
            self.response = self.sesh.get(self.url, timeout=10)
            if self.loc:
                msg = f"{self.qry} | {self.loc}"
            else:
                msg = f"{self.qry}" 
            self.log.info(f'{self.response.status_code} | {msg}')

        except requests.exceptions.ConnectionError:
            # SSH Tunnel may have died. 
            self.log.exception(f'SERP | Connection error | {self.serp_id}')

            # Reset SSH session
            if self.ssh_tunnel:
                self.ssh_tunnel.tunnel.kill()
                self.ssh_tunnel.open_tunnel()
                self.log.info(f'SERP | Restarted SSH tunnel | {self.serp_id}')
                time.sleep(10) # Allow time to establish connection

        except requests.exceptions.Timeout:
            # Connection timed out
            self.log.exception(f'SERP | Timeout error | {self.serp_id}')

        except Exception:
            # Honestly, who knows
            self.log.exception(f'SERP | Scraping error | {self.serp_id}')


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


    def search(self, qry, location='', serp_id=''):
        """Conduct a search and save HTML
        
        Args:
            qry (str): The search query
            location (str, optional): A location's Canonical Name.
            serp_id (str, optional): A unique identifier for this SERP
        """
        self.prepare_url(qry, location=location)
        self.serp_id = serp_id if serp_id else hash_id(qry + location)
        self.timestamp = utc_stamp()
        self.snapshot()
        self.handle_response()


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


    def save_serp(self, save_dir='.', append_to=''):
        """Save SERP to file

        Args:
            save_dir (str, optional): Save results as `save_dir/{serp_id}.json`
            append_to (str, optional): Append results to this file path
        """
        assert self.html, "Must conduct a search first"

        if append_to:
            # Keys to drop from object before saving
            exclude = ['response', 'sesh', 'ssh_tunnel', 'unzip',
                       'log', 'results', 'results_html']
            out_data = {k: v for k, v in vars(self).items() if k not in exclude}
            out_data['response_code'] = self.response.status_code
            out_data['html'] = out_data['html']

            if append_to:
                utils.write_lines([out_data], append_to)
        else:
            fp = os.path.join(save_dir, f'{self.serp_id}.html')
            with open(fp, 'w') as outfile:
                outfile.write(self.html)


    def parse_results(self, save_dir='.'):
        """Parse a SERP
        
        Args:
            save_dir (str, optional): Description
        """
        # Parse results, see parsers.py
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


    def save_response_as_html(self, filename=None, save_dir='.'):
        """Save response text as html

        Args:
            filename (str, optional): Filename to save as, defaults to `test_response_save_{datetime}.html`
            save_dir (str, optional): Directory to save to, defaults to current directory
        """
        if not filename:
            filename = f'response_{datetime.now().strftime("%Y%m%d%H%M%S")}.html'

        # Save response text
        if self.response.text:
            with open(os.path.join(save_dir, filename), 'w') as outfile:
                outfile.write(self.response.text)
        else:
            self.log.info(f'No response text for serp_id {self.serp_id}')

    