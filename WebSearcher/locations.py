import os
import csv
import base64
import string
import requests
from bs4 import BeautifulSoup

from . import logger
log = logger.Logger().start(__name__)

URL = 'https://developers.google.com/adwords/api/docs/appendix/geotargeting'

def get_all_urls(soup):
    a_divs = soup.find_all('a')
    all_urls = {a.attrs['href'] for a in a_divs if 'href' in a.attrs}
    return all_urls

def get_latest_url(url):
    # Get latest URL
    try:
        html = requests.get(url).content
        soup = BeautifulSoup(html, 'lxml')
        all_urls = get_all_urls(soup)
        geo_urls = [url for url in all_urls if 'geotargets' in url]

        # Get current CSV url and use as filename
        geo_url = sorted(geo_urls)[-1]
        full_url = 'https://developers.google.com' + geo_url
        return full_url

    except Exception:
        log.exception("Failed to retrieve location data's url")
    
def write_csv(fp, lines):
    with open(fp, 'w', encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerows(lines)

def download_locations(data_dir, url=URL, return_data=True):
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

    full_url = get_latest_url(url)
    fp = os.path.join(data_dir, full_url.split('/')[-1])

    # Check if the current version already exists
    if os.path.exists(fp):
        print(f'Version up to date: {fp}')
    # If it doesn't, download it
    else:
        try:
            print(f'Getting: {full_url}')
            response = requests.get(full_url)
            lines = response.content.decode('utf-8').split('\n')
            locations = [l for l in csv.reader(lines, delimiter=',')]
        except Exception:
            log.exception('Failed to retrieve location data')

        # Save
        print(f"saving csv: {fp}")
        write_csv(fp, locations)
        
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
