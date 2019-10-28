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
import os
import base64
import string
import requests
import pandas as pd
from bs4 import BeautifulSoup

from . import logger
log = logger.Logger().start(__name__)

url = 'https://developers.google.com/adwords/api/docs/appendix/geotargeting'

def get_all_urls(soup):
    a_divs = soup.find_all('a')
    all_urls = {a.attrs['href'] for a in a_divs if 'href' in a.attrs}    
    return all_urls

def download_locations(data_dir, url=url, return_data=True):
    """Download the latest locations data

    Checks if the current version already exists locally before downloading
    
    Args:
        data_dir (str): Where to save the data as a csv
        url (str, optional): Defaults to the current URL
    
    Raises:
        SystemExit: Exit if file exists

    Returns:
        None: Saves to file in the default or selected data_dir

    """
    data_dir = data_dir if data_dir else 'data/locations'
    os.makedirs(data_dir, exist_ok=True)

    # Get latest URL
    try:
        html = requests.get(url).content
        soup = BeautifulSoup(html, 'lxml')
        all_urls = get_all_urls(soup)
        geo_urls = [url for url in all_urls if 'geotargets' in url]

    except Exception:
        log.exception("Failed to retrieve location data's url")

    # Get current CSV url and use as filename
    geo_url = sorted(geo_urls)[-1]
    full_url = 'https://developers.google.com' + geo_url
    fp = os.path.join(data_dir, geo_url.split('/')[-1])

    # Check if the current version already exists
    if os.path.exists(fp):
        print(f'Version up to date: {geo_url}')
    else:
        # If it doesn't, download it
        try:
            print(f'Getting: {full_url}')
            locations = pd.read_csv(full_url)
        except Exception:
            log.exception('Failed to retrieve location data')

        # Save
        locations.to_csv(fp, index=False, encoding='utf-8')
        
        # Return
        if return_data:
            return locations


def get_location_id(canonical_name):
    """Get location ID for URL parameter 'uule'
    
    Returns the url parameter for a given location's Canonical Name
    
    Args:
        canonical_name (str): Canoncial Name for a location, see
        data downloaded using download_locations. Column name is 
        usually something like "Canonical Name" or "Canonical.Name". 
    
    Returns:
        str: The parameter key for selecting a location
    
    """
    uule_key = string.ascii_uppercase+string.ascii_lowercase+string.digits
    uule_key = uule_key + '-_' + uule_key + '-_' # Double length, repeating
    key = uule_key[len(canonical_name)]
    b64 = base64.b64encode(canonical_name.encode('utf-8')).decode('utf-8')
    return f'w+CAIQICI{key}{b64}'