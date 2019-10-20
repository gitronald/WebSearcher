# Copyright (C) 2017-2019 Ronald E. Robertson <rer@ronalderobertson.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
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

default_headers = {
    'Host': 'www.google.com',
    'Referer': 'https://www.google.com/',
    'Accept': '*/*'
}
default_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0'
default_encoding = 'gzip,deflate,br'
default_language = 'en-US,en;q=0.5'


class SearchEngine(object):
    """ Collect Search Engine Results Pages (SERPs)
    
    Location provided must be a "Canonical Name"

    """
    def __init__(self, 
        sesh=None, ssh_tunnel=None, 
        log_fp='', log_mode='a+',
        user_agent=default_ua, 
        accept_encoding=default_encoding,
        accept_language=default_language):
        """Initialize a `requests.Session` to conduct searches through or
        pass an existing one with an optional SSH tunnel.
        
        Args:
            sesh (None, optional): A `requests.Session` object.
            ssh_tunnel (None, optional): An SSH tunnel subprocess from `webutils`.
            log_fp (str, optional): A file to log function process output to.
            log_mode (str, optional): Write over the log file or append to it.
            user_agent (str, optional): User-Agent string to use in request
            accept_encoding (str, optional): Acceptable zips to return
        """

        self.url = 'https://www.google.com/search'
        self.params = {}

        # Set request headers - telling the server about you
        self.headers = default_headers
        self.headers['User-Agent'] = user_agent
        self.headers['Accept-Encoding'] = accept_encoding
        self.headers['Accept-Language'] = accept_language

        # Set a requests session
        self.sesh = sesh if sesh else wu.start_sesh(headers=self.headers)

        # Set a log file, prints to console by default
        self.log = logger.Logger(log_fp, log_mode).start(__name__)

        # Set an SSH tunnel - conducting the search from somewhere else
        self.ssh_tunnel = ssh_tunnel

        # Initialize data storage - search results and optionally their html
        self.html = None
        self.results = []
        self.results_html = []


    def set_location(self, canonical_name):
        """Set location using uule parameter derived from location name

        Credit for figuring this out goes to the author of the PHP version: 
        https://github.com/512banque/uule-grabber/blob/master/uule.php.

        See download_locations.py or ws.download_locations() to 
        download a csv of locations and their canonical names. 

        """
        self.params['uule'] = locations.get_location_id(canonical_name)

    def prepare_url(self, qry, location):
        """Prepare a query

        Set as original query and current query per default behavior in desktop 
        search
        
        Args:
            qry (str): Search query
            location (str): location name
        """
        self.qry = qry
        self.params['q'] = '+'.join(qry.split(' '))

        # Reset previous location
        if 'uule' in self.params:
            self.params.pop('uule')
        if location:
            self.set_location(location)

        param_str = wu.join_url_quote(self.params)
        return  f'{self.url}?{param_str}'
        
    def search(self, qry, location='', serp_id=''):
        """Conduct a search and save HTML
        
        Args:
            qry (str): The search query
            location (str, optional): A location's Canonical Name.
            serp_id (str, optional): A unique identifier for this SERP
        """
        self.prepare_search_params(qry, location=location)
        self.timestamp = pd.datetime.utcnow().isoformat()

        rand_id = sha224(self.timestamp.encode('utf-8')).hexdigest()
        self.serp_id = serp_id if serp_id else rand_id

        try:
            self.response = self.sesh.get(qry_url, timeout=10)
            self.log.info(f'{self.response.status_code} | Searching {qry}')

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
            self.log.info('Not brotli compressed')
            self.html = self.response.content
        except Exception:
            self.log.exception(f'Decompression error | serp_id : {self.serp_id}')
            self.html = self.response.content

    def save_serp(self, save_dir='.', append_to=''):
        """Save SERP as `{save_dir}/serp_id.html` or append with metadata to a file 
        
        Args:
            save_dir (str, optional): Save results as `save_dir/{serp_id}.json`
            append_to (str, optional): Append results to this file path
        """
        # Save SERP
        if not self.html:
            self.unzip_html()
        
        if append_to:
            # Keys to drop from object before saving
            exclude = ['response', 'sesh', 'ssh_tunnel', 
                       'log', 'results', 'results_html']
            out_data = {k: v for k, v in vars(self).items() if k not in exclude}
            out_data['response_code'] = self.response.status_code
            out_data['html'] = out_data['html'].decode('utf-8', 'ignore')

            with open(append_to, 'a+') as outfile:
                outfile.write(f'{json.dumps(out_data)}\n')

        else:
            fp = os.path.join(save_dir, f'{self.serp_id}.html')
            with open(fp, 'wb') as outfile:
                outfile.write(self.html)

    def parse_results(self, save_dir='.'):
        """Parse a SERP
        
        Args:
            save_dir (str, optional): Description
        """
        # Parse results, see parsers.py
        if not self.html:
            self.unzip_html()
        
        # Decode string
        self.html = self.html.decode('utf-8', 'ignore')

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
            self.log.info(f'No results to save for serp_id {self.serp_id}')
    
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
            