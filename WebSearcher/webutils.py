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
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

SoupElement = BeautifulSoup | Tag | NavigableString


def load_html(fp: str | os.PathLike[str], zipped: bool = False) -> str | bytes:
    """Load html file, with option for brotli decompression"""
    read_func = lambda i: brotli.decompress(i.read()) if zipped else i.read()
    read_type = 'rb' if zipped else 'r'
    with open(fp, read_type) as infile:
        return read_func(infile)


def load_soup(fp: str | os.PathLike[str], zipped: bool = False) -> BeautifulSoup:
    return make_soup(load_html(fp, zipped))


def start_sesh(
    headers: Mapping[str, str] | None = None,
    proxy_port: int | None = None,
) -> requests.Session:
    protocols = ['http', 'https']
    proxy_base = "socks5://127.0.0.1:"

    sesh = requests.Session()

    if headers: # Add headers to all requests
        sesh.headers.update(headers)

    if proxy_port: # Send all requests through an ssh tunnel
        proxies = {p: f'{proxy_base}{proxy_port}' for p in protocols}
        sesh.proxies.update(proxies)

    for protocol in protocols: # Auto retry if random connection error
        sesh.mount(protocol, requests.adapters.HTTPAdapter(max_retries=3))

    return sesh

# Misc -------------------------------------------------------------------------

def check_dict_value(d: Mapping[str, Any], key: str, value: Any) -> bool:
    """Check if a key exists in a dictionary and is equal to a input value"""
    return (d[key] == value) if key in d else False


# Parsing ----------------------------------------------------------------------

def strip_html_tags(string: str) -> str:
    """Strips HTML <tags>"""
    return re.sub('<[^<]+?>', '', string)

def make_soup(html: str | bytes | BeautifulSoup, parser: str = 'lxml') -> BeautifulSoup:
    """Create soup object"""
    if isinstance(html, BeautifulSoup):
        return html
    else:
        return BeautifulSoup(html, parser)

def has_captcha(soup: BeautifulSoup) -> bool:
    """Boolean for 'CAPTCHA' appearance in soup"""
    return True if soup.find(string=re.compile('CAPTCHA')) else False

def get_html_language(soup: BeautifulSoup) -> str:
    try:
        language = soup.html.attrs['lang']
    except Exception:
        language = ''
    return language

def parse_hashtags(text: str) -> list[str]:
    """Extract unique hashtags and strip surrounding punctuation"""
    hashtags = set([w for w in text.split() if w.startswith("#")])
    hashtags = [re.sub(r"(\W+)$", "", h, flags = re.UNICODE) for h in hashtags]
    return list(set(hashtags))


def parse_lang(soup: BeautifulSoup) -> str | None:
    """Parse language from html tags"""
    try:
        return soup.find('html').attrs['lang']
    except Exception as e:
        log.exception('Error while parsing language')
        return None


# Get divs, links, and text ----------------------------------------------------

def get_div(
    soup: BeautifulSoup | None,
    name: str | None,
    attrs: Mapping[str, Any] | None = None,
) -> SoupElement | None:
    """Utility for `soup.find(name)` with null attrs handling"""
    if not soup:
        return None
    return soup.find(name, attrs) if attrs else soup.find(name)

def get_text(
    soup: BeautifulSoup | None,
    name: str | None = None,
    attrs: Mapping[str, Any] | None = None,
    separator: str = " ",
    strip: bool = False,
) -> str | None:
    """Utility for `soup.find(name).text` with null name handling"""
    if not soup:
        return None
    div = get_div(soup, name, attrs) if name else soup
    if not div:
        return None
    text = div.get_text(separator=separator)
    return text.strip() if strip else text

def get_link(
    soup: BeautifulSoup | None,
    attrs: Mapping[str, Any] | None = None,
    key: str = 'href'
) -> str | None:
    """Utility for `soup.find('a')['href']` with null key handling"""
    link = get_div(soup, 'a', attrs)
    return link.attrs.get(key, None) if link else None

def get_link_list(
    soup: BeautifulSoup | None,
    attrs: Mapping[str, Any] | None = None,
    key: str = 'href',
    filter_empty: bool = True,
) -> list[str] | None:
    """Utility for `soup.find_all('a')['href']` with null key handling"""
    links = find_all_divs(soup, 'a', attrs, filter_empty)
    return [link.attrs.get(key, None) for link in links] if links else None

def find_all_divs(
    soup: BeautifulSoup | None,
    name: str,
    attrs: Mapping[str, Any] | None = None,
    filter_empty: bool = True,
) -> list[SoupElement]:
    if not soup:
        return []
    divs = soup.find_all(name, attrs) if attrs else soup.find_all(name)
    divs = filter_empty_divs(divs) if filter_empty else divs
    return list(divs)

def filter_empty_divs(divs: Iterable[SoupElement]) -> list[SoupElement]:
    filtered: list[SoupElement] = []
    for candidate in divs:
        if not candidate:
            continue
        text_content = candidate.text if hasattr(candidate, 'text') else str(candidate)
        if text_content.strip() != '':
            filtered.append(candidate)
    return filtered

def find_children(
    soup: BeautifulSoup | None,
    name: str,
    attrs: Mapping[str, Any] | None = None,
    filter_empty: bool = False,
) -> Iterable[SoupElement]:
    """Find all children of a div with a given name and attribute"""
    div = get_div(soup, name, attrs)
    divs = div.children if div else []
    divs = filter_empty_divs(divs) if filter_empty else divs
    return divs


# URLs -------------------------------------------------------------------------

def join_url_quote(quote_dict: Mapping[str, str]) -> str:
    return '&'.join([f'{k}={v}' for k, v in quote_dict.items()])

def encode_param_value(value: str) -> str:
    return urlparse.quote_plus(value)

def url_unquote(url: str) -> str:
    return urlparse.unquote(url)

def get_domain(url: str | None) -> str:
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

def extract_html_json(
    data_fp: str | os.PathLike[str],
    extract_to: str | os.PathLike[str],
    id_col: str,
) -> None:
    """Save HTML to directory for viewing"""
    os.makedirs(extract_to, exist_ok=True)
    data = utils.read_lines(data_fp)
    for row in data:
        fp = os.path.join(extract_to, row[id_col] + '.html')
        with open(fp, 'wb') as outfile:
            outfile.write(row['html'])

def split_styles(soup: BeautifulSoup) -> list[str] | None:
    """Extract embedded CSS """
    
    def split_style(style):
        if style.string:
            return style.string.replace('}', '}\n').split('\n')
        else:
            return None

    styles = soup.find_all('style')
    if styles:
        style_chunks = [chunk for chunk in map(split_style, styles) if chunk is not None]
        return sum(style_chunks, [])
    else:
        return None


# SSH -------------------------------------------------------------------------

class SSH:
    """ Create SSH cmd and tunnel objects """
    def __init__(
        self,
        user: str = 'ubuntu',
        port: int = 6000,
        ip: str = '',
        keyfile: str = '',
    ) -> None:
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
        self.tunnel: subprocess.Popen[bytes] | None = None
    
    def open_tunnel(self) -> None:
        self.tunnel = subprocess.Popen(self.cmd, shell=False)

def generate_ssh_tunnels(
    ips: Sequence[str],
    ports: Sequence[int],
    keyfile: str,
) -> list[SSH]:
    """ Generate SSH tunnels for each (IP, port) combination"""

    def generate_ssh_tunnel(ip: str, port: int, keyfile: str = keyfile) -> SSH:
        ssh_tunnel = SSH(ip=ip, port=port, keyfile=keyfile)
        subprocess.call(['chmod', '600', keyfile])
        log.info(f'{ssh_tunnel.cmd_str}')
        ssh_tunnel.open_tunnel()
        atexit.register(exit_handler, ssh_tunnel) # Always kill tunnels on exit
        return ssh_tunnel

    return [generate_ssh_tunnel(ip, port) for ip, port in zip(ips, ports)]

def exit_handler(ssh: SSH) -> None:
    log.info(f'Killing: {ssh.machine} on port: {ssh.port}')
    if ssh.tunnel:
        ssh.tunnel.kill()