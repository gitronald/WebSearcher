import atexit
import hashlib
import re
import subprocess
import urllib.parse as urlparse
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import brotli
import orjson
import requests
import tldextract
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from . import logger

log = logger.Logger().start(__name__)

SoupElement = BeautifulSoup | Tag | NavigableString

# Files ------------------------------------------------------------------------


def read_lines(fp: str | Path):
    fp = Path(fp)
    with open(fp) as infile:
        if fp.suffix == ".json":
            return [orjson.loads(line) for line in infile]
        else:
            return [line.strip() for line in infile]


def write_lines(iter_data, fp: str | Path, overwrite=False):
    fp = Path(fp)
    mode = "w" if overwrite else "a+"

    with open(fp, mode) as outfile:
        for data in iter_data:
            if fp.suffix == ".json":
                line_output = orjson.dumps(data).decode("utf-8")
            else:
                line_output = data
            outfile.write(f"{line_output}\n")


def load_html(fp: str | Path, zipped: bool = False) -> str | bytes:
    """Load html file, with option for brotli decompression"""
    read_type = "rb" if zipped else "r"
    with open(fp, read_type) as infile:
        return brotli.decompress(infile.read()) if zipped else infile.read()


def load_soup(fp: str | Path, zipped: bool = False) -> BeautifulSoup:
    return make_soup(load_html(fp, zipped))


# Strings ----------------------------------------------------------------------


def get_between_parentheses(s, regex=r"\((.*?)\)"):
    return re.search(regex, s).group(1)


# Hashing ----------------------------------------------------------------------


def hash_id(s):
    return hashlib.sha224(s.encode("utf-8")).hexdigest()


# Parsing ----------------------------------------------------------------------


def make_soup(html: str | bytes | BeautifulSoup, parser: str = "lxml") -> BeautifulSoup:
    """Create soup object"""
    if isinstance(html, BeautifulSoup):
        return html
    else:
        return BeautifulSoup(html, parser)


def has_captcha(soup: BeautifulSoup) -> bool:
    """Boolean for 'CAPTCHA' appearance in soup"""
    return True if soup.find(string=re.compile("CAPTCHA")) else False


def check_dict_value(d: Mapping[str, Any], key: str, value: Any) -> bool:
    """Check if a key exists in a dictionary and is equal to a input value"""
    return (d[key] == value) if key in d else False


# Get divs, links, and text ----------------------------------------------------


def get_div(
    soup: Tag | None,
    name: str | None,
    attrs: Mapping[str, Any] | None = None,
) -> SoupElement | None:
    """Utility for `soup.find(name)` with null attrs handling"""
    if not soup:
        return None
    return soup.find(name, attrs) if attrs else soup.find(name)


def get_text(
    soup: Tag | None,
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
    soup: Tag | None, attrs: Mapping[str, Any] | None = None, key: str = "href"
) -> str | None:
    """Utility for `soup.find('a')['href']` with null key handling"""
    link = get_div(soup, "a", attrs)
    return link.attrs.get(key, None) if link else None


def get_link_list(
    soup: Tag | None,
    attrs: Mapping[str, Any] | None = None,
    key: str = "href",
    filter_empty: bool = True,
) -> list[str] | None:
    """Utility for `soup.find_all('a')['href']` with null key handling"""
    links = find_all_divs(soup, "a", attrs, filter_empty)
    return [link.attrs.get(key, None) for link in links] if links else None


def get_text_by_selectors(
    soup: Tag | None,
    selectors: Sequence[tuple[str, Mapping[str, Any]]] | None = None,
    strip: bool = False,
) -> str | None:
    """Get text by trying multiple selectors, return first non-null"""
    if not soup or not selectors:
        return None
    for name, attrs in selectors:
        text = get_text(soup, name, attrs, strip=strip)
        if text:
            return text
    return None


def find_by_selectors(
    soup: Tag | None,
    selectors: Sequence[Mapping[str, Any]] | None = None,
) -> SoupElement | None:
    """Find first matching element across multiple selectors.

    Each selector is a dict of kwargs forwarded to ``soup.find(**sel)``,
    e.g. ``{"name": "div", "attrs": {"id": "foo"}}``. Iteration is lazy:
    later selectors are not evaluated once a match is found.
    """
    if not soup or not selectors:
        return None
    for sel in selectors:
        match = soup.find(**sel)
        if match:
            return match
    return None


def find_all_divs(
    soup: Tag | None,
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
        text_content = candidate.text if hasattr(candidate, "text") else str(candidate)
        if text_content.strip() != "":
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
    return "&".join([f"{k}={v}" for k, v in quote_dict.items()])


def encode_param_value(value: str) -> str:
    return urlparse.quote_plus(value)


def url_unquote(url: str) -> str:
    return urlparse.unquote(url)


def get_domain(url: str | None) -> str:
    """Extract a full domain from a url, drop www"""
    if not url:
        return ""
    domain = tldextract.extract(url)
    without_subdomain = ".".join([domain.domain, domain.suffix])
    with_subdomain = ".".join([domain.subdomain, domain.domain, domain.suffix])
    if domain.subdomain:
        domain_str = without_subdomain if domain.subdomain == "www" else with_subdomain
    else:
        domain_str = without_subdomain
    return domain_str


# Sessions ---------------------------------------------------------------------


def start_sesh(
    headers: Mapping[str, str] | None = None,
    proxy_port: int | None = None,
) -> requests.Session:
    protocols = ["http", "https"]
    proxy_base = "socks5://127.0.0.1:"

    sesh = requests.Session()

    if headers:  # Add headers to all requests
        sesh.headers.update(headers)

    if proxy_port:  # Send all requests through an ssh tunnel
        proxies = {p: f"{proxy_base}{proxy_port}" for p in protocols}
        sesh.proxies.update(proxies)

    for protocol in protocols:  # Auto retry if random connection error
        sesh.mount(protocol, requests.adapters.HTTPAdapter(max_retries=3))

    return sesh


# SSH --------------------------------------------------------------------------


class SSH:
    """Create SSH cmd and tunnel objects"""

    def __init__(
        self,
        user: str = "ubuntu",
        port: int = 6000,
        ip: str = "",
        keyfile: str = "",
    ) -> None:
        self.user = user
        self.keyfile = keyfile
        self.port = port
        self.ip = ip
        self.machine = f"{self.user}@{self.ip}"
        self.cmd = [
            "ssh",
            "-i",
            self.keyfile,
            "-ND",
            f"127.0.0.1:{self.port}",
            "-o",
            "StrictHostKeyChecking=no",
            self.machine,
        ]
        self.cmd_str = " ".join(self.cmd)
        self.tunnel: subprocess.Popen[bytes] | None = None

    def open_tunnel(self) -> None:
        self.tunnel = subprocess.Popen(self.cmd, shell=False)


def generate_ssh_tunnels(
    ips: Sequence[str],
    ports: Sequence[int],
    keyfile: str,
) -> list[SSH]:
    """Generate SSH tunnels for each (IP, port) combination"""

    def generate_ssh_tunnel(ip: str, port: int, keyfile: str = keyfile) -> SSH:
        ssh_tunnel = SSH(ip=ip, port=port, keyfile=keyfile)
        subprocess.call(["chmod", "600", keyfile])
        log.info(f"{ssh_tunnel.cmd_str}")
        ssh_tunnel.open_tunnel()
        atexit.register(exit_handler, ssh_tunnel)  # Always kill tunnels on exit
        return ssh_tunnel

    return [generate_ssh_tunnel(ip, port) for ip, port in zip(ips, ports)]


def exit_handler(ssh: SSH) -> None:
    log.info(f"Killing: {ssh.machine} on port: {ssh.port}")
    if ssh.tunnel:
        ssh.tunnel.kill()
