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
import pandas as pd
from hashlib import sha224
from datetime import datetime

default_headers = {
    'Host': 'www.google.com',
    'Referer': 'https://www.google.com/',
    'Accept': '*/*'
}
default_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0'
default_encoding = 'gzip,deflate,br'
default_language = 'en-US,en;q=0.5'

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
        user_agent=default_ua, 
        accept_encoding=default_encoding,
        accept_language=default_language,
        unzip=False):
        """Initialize a `requests.Session` to conduct searches through or
        pass an existing one with an optional SSH tunnel.
        
        Args:
            sesh (None, optional): A `requests.Session` object.
            ssh_tunnel (None, optional): An SSH tunnel subprocess from `webutils`.
            log_fp (str, optional): A file to log function process output to.
            log_mode (str, optional): Write over the log file or append to it.
            user_agent (str, optional): User-Agent string to use in request
            accept_encoding (str, optional): Response encodings to accept
            accept_language (str, optional): Response language to accept
        """

        self.base_url = 'https://www.google.com/search'
        self.params = {}

        # Set request headers - telling the server about you
        self.headers = default_headers
        self.headers['User-Agent'] = user_agent
        self.headers['Accept-Encoding'] = accept_encoding
        self.headers['Accept-Language'] = accept_language

        # Set a requests session
        self.sesh = sesh if sesh else wu.start_sesh(headers=self.headers)

        # Set a log file, prints to console by default
        self.log = logger.Logger(
            file_name=log_fp, 
            file_mode=log_mode
        ).start(__name__)

        # Set an SSH tunnel - conducting the search from somewhere else
        self.ssh_tunnel = ssh_tunnel

        # Initialize data storage - search results and optionally their html
        self.html = None
        self.unzip = unzip
        self.results = []
        self.results_html = []


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
        try: 
            self.html = brotli.decompress(self.response.content)
        except brotli.error:
            self.html = self.response.content
        except Exception:
            self.log.exception(f'Decompression error | serp_id : {self.serp_id}')
            self.html = self.response.content

    def save_serp(self, save_dir='.', append_to='', sql_table='', sql_conn=None):
        """Save SERP to file or SQL table
        
        Args:
            save_dir (str, optional): Save results as `save_dir/{serp_id}.json`
            append_to (str, optional): Append results to this file path
            sql_table (str, optional): A SQL table name 
            sql_conn (Object, optional): A SQL connection
        """
        assert self.html, "Must conduct a search first"
        
        if append_to or sql_conn:
            # Keys to drop from object before saving
            exclude = ['response', 'sesh', 'ssh_tunnel', 'unzip',
                       'log', 'results', 'results_html']
            out_data = {k: v for k, v in vars(self).items() if k not in exclude}
            out_data['response_code'] = self.response.status_code
            out_data['html'] = out_data['html']

            if append_to:
                utils.write_lines([out_data], append_to)
            elif sql_table and sql_conn:
                utils.write_sql_row(out_data, table=sql_table, conn=sql_conn)
                
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
    
    def scrape_results_html(self, save_dir='.', append_to=''):
        """Scrape and save all unique, non-internal URLs parsed from the SERP
        
        Args:
            save_dir (str, optional): Save results html as `save_dir/results_html/{serp_id}.json`
            append_to (str, optional): Append results html to this file path
        """

        if not self.results:
            self.log.info(f'No results to scrape for serp_id {self.serp_id}')
        else:
            results = pd.DataFrame(self.results)

            if 'url' in results.columns:

                # Prepare session
                keep_headers = ['User-Agent']
                headers = {k:v for k,v in self.headers.items() if k in keep_headers}
                if self.ssh_tunnel:
                    result_sesh = wu.start_sesh(headers=headers, proxy_port=self.ssh_tunnel.port)
                else:
                    result_sesh = wu.start_sesh(headers=headers)

                # Get all unique result urls
                mask = ((~results.url.duplicated()) & (~pd.isnull(results.url)))
                cols = ['serp_id', 'serp_rank', 'url']
                result_urls = results[mask][cols].to_dict(orient='records')

                # Scrape results HTML
                for result in result_urls:
                    try:
                        response = result_sesh.get(result['url'], timeout=10)
                        result['html'] = response.content.decode('utf-8', 'ignore')

                    except requests.exceptions.TooManyRedirects:
                        result['html'] = 'error_redirects'
                        self.log.exception(f"Results | Redirects error | {result['serp_id']} | {result['url']}")

                    except requests.exceptions.Timeout:
                        result['html'] = 'error_timeout'
                        self.log.exception(f"Results | Timeout error | {result['serp_id']} | {result['url']}")

                    except requests.exceptions.ConnectionError: 
                        result['html'] = 'error_connection'
                        self.log.exception(f"Results | Connection error | {result['serp_id']} | {result['url']}")

                        # SSH Tunnel may have died, reset SSH session
                        if self.ssh_tunnel:
                            self.ssh_tunnel.tunnel.kill()
                            self.ssh_tunnel.open_tunnel()
                            self.log.info('Results | Restarted SSH tunnel')
                            time.sleep(10) # Allow time to establish connection

                    except Exception:
                        result['html'] = 'error_unknown'
                        self.log.exception(f"Results | Scraping error | {result['serp_id']} | {result['url']}")

                    self.results_html.append(result)

                if append_to:
                    utils.write_lines(self.results_html, append_to)
                else:
                    # Create directory using serp_id
                    fp = os.path.join(save_dir, 'results_html', f'{self.serp_id}.json')
                    utils.write_lines(self.results_html, fp)
