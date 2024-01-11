import os
import io
import csv
import base64
import string
import zipfile
import requests
from bs4 import BeautifulSoup

from . import logger
from . import webutils as wu
log = logger.Logger().start(__name__)


def get_location_id(canonical_name: str) -> str:
    """Get location ID for URL parameter 'uule'
    
    Returns the url parameter for a given location's Canonical Name
    
    Args:
        canonical_name (str): The "Canoncial Name" for a location. Use 
        download_locations to obtain file containing all options. Column name 
        is usually something like "Canonical Name" or "Canonical.Name". 
    
    Returns:
        str: The uule parameter key for selecting a location
    
    """
    uule_key = string.ascii_uppercase+string.ascii_lowercase+string.digits
    uule_key = uule_key + '-_' + uule_key + '-_' # Double length, repeating
    key = uule_key[len(canonical_name)]
    b64 = base64.b64encode(canonical_name.encode('utf-8')).decode('utf-8')
    return f'w+CAIQICI{key}{b64}'


def download_locations(
        data_dir: str = "data/locations", 
        url: str = "https://developers.google.com/adwords/api/docs/appendix/geotargeting"
    ) -> None:
    """Download the latest geolocations, check if already exists locally first.

    Args:
        data_dir (str): Where to save the data as a csv
        url (str, optional): Defaults to the current URL

    Returns:
        None: Saves to file in the default or selected data_dir

    """
    os.makedirs(data_dir, exist_ok=True)

    full_url = get_latest_url(url)
    fp = os.path.join(data_dir, full_url.split('/')[-1])
    fp_unzip = fp.replace('.zip', '')

    # Check if the current version already exists
    if os.path.exists(fp):
        print(f"Version up to date: {fp}")
    elif os.path.exists(fp_unzip):
        print(f"Version up to date: {fp_unzip}")
    else:
        # Download and save
        try:
            print(f'Getting: {full_url}')
            response = requests.get(full_url)
        except Exception:
            log.exception('Failed to retrieve location data')

        if fp.endswith('.zip'):
            save_zip_response(response, fp_unzip)
        else:
            lines = response.content.decode('utf-8').split('\n')
            locations = [l for l in csv.reader(lines, delimiter=',')]
            write_csv(fp_unzip, locations)


def get_latest_url(url:str):
    try:
        html = requests.get(url).content
        soup = wu.make_soup(html)
        geo_urls = [url for url in wu.get_link_list(soup) if 'geotargets' in url]

        # Get current CSV url and use as filename
        geo_url = sorted(geo_urls)[-1]
        full_url = 'https://developers.google.com' + geo_url
        return full_url

    except Exception:
        log.exception("Failed to retrieve location data url")


def get_all_urls(soup):
    a_divs = soup.find_all('a')
    all_urls = {a.attrs['href'] for a in a_divs if 'href' in a.attrs}    
    return all_urls


def save_zip_response(response: requests.Response, fp: str) -> None:
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        for member in zip_ref.namelist():
            if member.endswith('.csv'):
                with zip_ref.open(member) as csv_file:
                    with open(fp, 'w', encoding="utf-8") as outfile:
                        reader = csv.reader(io.TextIOWrapper(csv_file,'utf-8'))
                        writer = csv.writer(outfile)
                        writer.writerows(reader)
                    print(f"saved: {fp}")


def write_csv(fp: str, lines: list) -> None:
    with open(fp, 'w', encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerows(lines)
    print(f"saved: {fp}")

