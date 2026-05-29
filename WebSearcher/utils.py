import atexit
import hashlib
import re
import subprocess
import urllib.parse as urlparse
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

import brotli
import orjson
import requests
import tldextract
from selectolax.lexbor import LexborNode as Node

from . import logger
from ._slx import (
    _build_css,
    has_text,
    make_soup,
    subtree_css,
    subtree_first,
)
from ._slx import get_text as _slx_get_text

log = logger.Logger().start(__name__)


class Selector(NamedTuple):
    """A bs4 tag selector: a tag name and optional attribute filter."""

    name: str | None
    attrs: dict[str, Any] | None = None


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


def load_soup(fp: str | Path, zipped: bool = False) -> Node:
    return make_soup(load_html(fp, zipped))


# Strings ----------------------------------------------------------------------


def get_between_parentheses(s, regex=r"\((.*?)\)"):
    match = re.search(regex, s)
    return match.group(1) if match else ""


def slugify(text: str, sep: str = "_") -> str:
    """Whitespace-robust slug: collapse all whitespace runs to a single separator.

    Equivalent to ``sep.join(text.split())`` -- handles ASCII space, tabs,
    non-breaking space, and other unicode whitespace uniformly, so the result is
    independent of incidental whitespace in source ``get_text`` output. The
    parsers that derive a ``sub_type`` from a heading should use this rather than
    a bare ``.replace(" ", sep)`` (which only normalizes ASCII space).
    """
    return sep.join(text.split())


# Hashing ----------------------------------------------------------------------


def hash_id(s):
    return hashlib.sha224(s.encode("utf-8")).hexdigest()


# Parsing ----------------------------------------------------------------------


def has_captcha(soup: Node | None) -> bool:
    """Boolean for 'CAPTCHA' appearance in the document text.

    Uses ``soup.text(deep=True)`` (single C-level walk over the document) and a
    substring check; cheaper than walking text nodes individually.
    """
    if soup is None:
        return False
    return "CAPTCHA" in (soup.text(deep=True) or "")


def check_dict_value(d: Mapping[str, Any], key: str, value: Any) -> bool:
    """Check if a key exists in a dictionary and is equal to a input value"""
    return (d[key] == value) if key in d else False


# Get divs, links, and text ----------------------------------------------------


def get_div(
    soup: Node | None,
    name: str | None,
    attrs: Mapping[str, Any] | None = None,
) -> Node | None:
    """``soup.find(name, attrs)`` -- descendants only (excludes ``soup``)."""
    if soup is None:
        return None
    css = _build_css(name, dict(attrs) if attrs else {})
    return subtree_first(soup, css) if css is not None else None


def get_text(
    soup: Node | None,
    name: str | None = None,
    attrs: Mapping[str, Any] | None = None,
    separator: str = " ",
    strip: bool = False,
) -> str | None:
    """``soup.find(name, attrs).get_text(separator, strip)`` with null handling."""
    if soup is None:
        return None
    if name is not None:
        soup = get_div(soup, name, attrs)
        if soup is None:
            return None
    return _slx_get_text(soup, separator, strip)


def get_link(
    soup, attrs: Mapping[str, Any] | None = None, key: str = "href"
) -> str | None:
    """First descendant anchor's ``href`` (or other attribute), or ``None``."""
    link = get_div(soup, "a", attrs)
    if link is None:
        return None
    value = link.attributes.get(key)
    return str(value) if value is not None else None


def get_link_list(
    soup,
    attrs: Mapping[str, Any] | None = None,
    key: str = "href",
    filter_empty: bool = True,
) -> list[str] | None:
    """All descendant anchor ``href``s -- skips anchors missing the attribute."""
    links = find_all_divs(soup, "a", attrs, filter_empty)
    if not links:
        return None
    out = [str(link.attributes[key]) for link in links if link.attributes.get(key)]
    return out or None


def get_text_by_selectors(
    soup,
    selectors: Sequence["Selector"] | None = None,
    strip: bool = False,
) -> str | None:
    """Get text by trying multiple selectors, return first non-null."""
    if soup is None or not selectors:
        return None
    for sel in selectors:
        text = get_text(soup, sel.name, sel.attrs, strip=strip)
        if text:
            return text
    return None


def find_by_selectors(
    soup,
    selectors: Sequence[Mapping[str, Any]] | None = None,
) -> Node | None:
    """First matching element across multiple ``{"name":..., "attrs":...}`` dicts."""
    if soup is None or not selectors:
        return None
    for sel in selectors:
        match = get_div(soup, sel.get("name"), sel.get("attrs"))
        if match is not None:
            return match
    return None


def find_all_divs(
    soup: Node | None,
    name: str | None,
    attrs: Mapping[str, Any] | None = None,
    filter_empty: bool = True,
) -> list[Node]:
    """All descendants matching the bs4-style ``(name, attrs)`` query."""
    if soup is None:
        return []
    css = _build_css(name, dict(attrs) if attrs else {})
    if css is None:
        return []
    divs = subtree_css(soup, css)
    return [d for d in divs if has_text(d)] if filter_empty else divs


def filter_empty_divs(divs: Iterable[Node]) -> list[Node]:
    """Keep elements whose subtree contains at least one non-whitespace fragment."""
    return [d for d in divs if d is not None and has_text(d)]


def find_children(
    soup,
    name: str,
    attrs: Mapping[str, Any] | None = None,
    filter_empty: bool = False,
) -> Iterable[Node]:
    """Direct element children of the first descendant matching ``(name, attrs)``."""
    div = get_div(soup, name, attrs)
    if div is None:
        return []
    children = list(div.iter(include_text=False))
    return filter_empty_divs(children) if filter_empty else children


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
