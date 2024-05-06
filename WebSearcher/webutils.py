""" webutils (wu): A useful collection of web utilities

Note on using socks5h, hostname resolution
https://stackoverflow.com/questions/12601316/how-to-make-python-requests-work-via-socks-proxy
"""
from . import utils
from . import logger
log = logger.Logger().start(__name__)

import os
import re
import atexit
import brotli
import requests
import subprocess
import tldextract
import urllib.parse as urlparse
from bs4 import BeautifulSoup


def load_html(fp, zipped=False):
    """Load html file, with option for brotli decompression"""
    read_func = lambda i: brotli.decompress(i.read()) if zipped else i.read()
    read_type = 'rb' if zipped else 'r'
    with open(fp, read_type) as infile:
        return read_func(infile)


def load_soup(fp, zipped=False):
    return make_soup(load_html(fp, zipped))


def start_sesh(headers=None, proxy_port=None):
    protocols = ['http', 'https']
    proxy_base = "socks5://127.0.0.1:"

    sesh = requests.Session()

    if headers: # Add headers to all requests
        sesh.headers.update(headers)

    if proxy_port: # Send all requests through an ssh tunnel
        proxies = {p: f'{proxy_base}{p}' for p in protocols}
        sesh.proxies.update(proxies)

    for protocol in protocols: # Auto retry if random connection error
        sesh.mount(protocol, requests.adapters.HTTPAdapter(max_retries=3))

    return sesh

# Misc -------------------------------------------------------------------------

def check_dict_value(d, key, value):
    """Check if a key exists in a dictionary and is equal to a input value"""
    return (d[key] == value) if key in d else False


# Parsing ----------------------------------------------------------------------

def strip_html_tags(string):
    """Strips HTML <tags>"""
    return re.sub('<[^<]+?>', '', string)

def make_soup(html, parser='lxml'):
    """Create soup object"""
    return BeautifulSoup(html, parser)

def has_captcha(soup):
    """Boolean for 'CAPTCHA' appearance in soup"""
    return True if soup.find(text=re.compile('CAPTCHA')) else False

def get_html_language(soup):
    try:
        language = soup.html.attrs['lang']
    except Exception:
        language = ''
    return language

def parse_hashtags(text):
    """Extract unique hashtags and strip surrounding punctuation"""
    hashtags = set([w for w in text.split() if w.startswith("#")])
    hashtags = [re.sub(r"(\W+)$", "", h, flags = re.UNICODE) for h in hashtags]
    return list(set(hashtags))


def parse_lang(soup):
    """Parse language from html tags"""
    try:
        return soup.find('html').attrs['lang']
    except Exception as e:
        log.exception('Error while parsing language')
        return None


# Get divs, links, and text ----------------------------------------------------

def get_div(soup: BeautifulSoup, name: str, attrs: dict = {}) -> BeautifulSoup:
    """Utility for `soup.find(name)` with null attrs handling"""
    return soup.find(name, attrs) if attrs else soup.find(name)

def get_text(soup, name: str=None, attrs: dict={}, separator:str=" ") -> str:
    """Utility for `soup.find(name).text` with null name handling"""
    div = get_div(soup, name, attrs) if name else soup
    return div.get_text(separator=separator) if div else None

def get_link(soup: BeautifulSoup, attrs: dict = {}, key: str = 'href') -> str:
    """Utility for `soup.find('a')['href']` with null key handling"""
    link = get_div(soup, 'a', attrs)
    return link.attrs.get(key, None) if link else None

def get_link_list(soup: BeautifulSoup, attrs: dict = {}, key: str = 'href') -> list:
    """Utility for `soup.find_all('a')['href']` with null key handling"""
    links = find_all_divs(soup, 'a', attrs)
    return [link.attrs.get(key, None) for link in links] if links else None

def find_all_divs(soup: BeautifulSoup, name: str, attrs: dict = {}, filter_empty: bool = True) -> list:
    divs = soup.find_all(name, attrs) if attrs else soup.find_all(name)
    if filter_empty:
        divs = [c for c in divs if c]
        divs = [c for c in divs if c.text != '']
    return divs

def find_children(soup, name: str, attrs: dict = {}) -> list:
    """Find all children of a div with a given name and attribute"""
    div = get_div(soup, name, attrs)
    return div.children if div else []


# URLs -------------------------------------------------------------------------

def join_url_quote(quote_dict):
    return '&'.join([f'{k}={v}' for k, v in quote_dict.items()])

def encode_param_value(value):
    return urlparse.quote_plus(value)

def url_unquote(url):
    return urlparse.unquote(url)

def get_domain(url):
    """Extract a full domain from a url, drop www"""
    if not url:
        return ''
    domain = tldextract.extract(url)
    without_subdomain = '.'.join([domain.domain, domain.suffix])
    with_subdomain = '.'.join([domain.subdomain, domain.domain, domain.suffix])
    if domain.subdomain:
        domain_str = without_subdomain if domain.subdomain=='www' else with_subdomain
    else:
        domain_str = without_subdomain
    return domain_str


# Misc -------------------------------------------------------------------------

def extract_html_json(data_fp, extract_to, id_col):
    """Save HTML to directory for viewing"""
    os.makedirs(extract_to, exist_ok=True)
    data = utils.read_lines(data_fp)
    for row in data:
        fp = os.path.join(extract_to, row[id_col] + '.html')
        with open(fp, 'wb') as outfile:
            outfile.write(row['html'])

def split_styles(soup):
    """Extract embedded CSS """
    
    def split_style(style):
        if style.string:
            return style.string.replace('}', '}\n').split('\n')
        else:
            return None

    styles = soup.find_all('style')
    if styles:
        return sum(list(map(split_style, styles)), [])
    else:
        return None


# SSH -------------------------------------------------------------------------

class SSH:
    """ Create SSH cmd and tunnel objects """
    def __init__(self, user='ubuntu', port=6000, ip='', keyfile=''):
        self.user = user
        self.keyfile = keyfile
        self.port = port
        self.ip = ip
        self.machine = f'{self.user}@{self.ip}'
        self.cmd = ['ssh', 
            '-i', self.keyfile, 
            '-ND', f'127.0.0.1:{self.port}',
            '-o','StrictHostKeyChecking=no', 
            self.machine
        ]
        self.cmd_str = ' '.join(self.cmd)
    
    def open_tunnel(self):
        self.tunnel = subprocess.Popen(self.cmd, shell=False)

def generate_ssh_tunnels(ips, ports, keyfile):
    """ Generate SSH tunnels for each (IP, port) combination"""

    def generate_ssh_tunnel(ip, port, keyfile=keyfile):
        ssh_tunnel = SSH(ip=ip, port=port, keyfile=keyfile)
        subprocess.call(['chmod', '600', keyfile])
        log.info(f'{ssh_tunnel.cmd_str}')
        ssh_tunnel.open_tunnel()
        atexit.register(exit_handler, ssh_tunnel) # Always kill tunnels on exit

    return [generate_ssh_tunnel(ip, port) for ip, port in zip(ips, ports)]

def exit_handler(ssh):
    log.info(f'Killing: {ssh.machine} on port: {ssh.port}')
    ssh.tunnel.kill()