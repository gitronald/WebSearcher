import hashlib
import logging
import re
import subprocess
import urllib.parse as urlparse
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import brotli
import orjson
import tldextract
from selectolax.lexbor import LexborNode as Node

from ._slx import has_text, make_soup

log = logging.getLogger(__name__)


# Files ------------------------------------------------------------------------
# Text files are always UTF-8: SERP HTML and orjson output are UTF-8, and the
# locale default (cp1252 on Windows) would corrupt or reject them.


def read_lines(fp: str | Path):
    fp = Path(fp)
    with open(fp, encoding="utf-8") as infile:
        if fp.suffix == ".json":
            return [orjson.loads(line) for line in infile]
        else:
            return [line.strip() for line in infile]


def write_lines(iter_data: Iterable[Any], fp: str | Path, overwrite: bool = False) -> None:
    fp = Path(fp)
    fp.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "a+"

    with open(fp, mode, encoding="utf-8") as outfile:
        for data in iter_data:
            if fp.suffix == ".json":
                line_output = orjson.dumps(data).decode("utf-8")
            else:
                line_output = data
            outfile.write(f"{line_output}\n")


def load_html(fp: str | Path, zipped: bool = False) -> str | bytes:
    """Load html file, with option for brotli decompression"""
    if zipped:
        with open(fp, "rb") as infile:
            return brotli.decompress(infile.read())
    with open(fp, encoding="utf-8") as infile:
        return infile.read()


def load_soup(fp: str | Path, zipped: bool = False) -> Node:
    return make_soup(load_html(fp, zipped))


# Strings ----------------------------------------------------------------------


def get_between_parentheses(s: str, regex: str = r"\((.*?)\)") -> str:
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


def hash_id(s: str) -> str:
    return hashlib.sha224(s.encode("utf-8")).hexdigest()


# Time -------------------------------------------------------------------------


def utc_timestamp() -> str:
    """Naive UTC ISO-8601 timestamp (``2026-10-16T20:18:00.123456``), the
    ``timestamp`` format both searcher backends record on a response."""
    return datetime.now(UTC).replace(tzinfo=None).isoformat()


# Parsing ----------------------------------------------------------------------


def is_sorry_redirect(url: str | None) -> bool:
    """Boolean for a Google /sorry/ (CAPTCHA challenge) redirect URL.

    Google redirects blocked requests to https://www.google.com/sorry/index?...
    -- the URL is a CAPTCHA signal even when the page HTML was never captured.
    The block page is also served from other Google hosts (ccTLDs like
    google.co.uk, historically ipv4.google.com), so match any google-registered
    domain with a /sorry path.
    """
    if not url:
        return False
    parts = urlparse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    if tldextract.extract(parts.netloc).domain != "google":
        return False
    return parts.path == "/sorry" or parts.path.startswith("/sorry/")


def has_captcha(soup: Node | None, html: str | None = None) -> bool:
    """Boolean for 'CAPTCHA' appearance in the document text.

    If ``html`` (the raw markup) is provided, a substring check rules out the
    common no-captcha case without a document text walk. Falls back to
    ``soup.text(deep=True)`` so script/style/template content doesn't
    false-positive on JS that happens to contain the literal.
    """
    if html is not None and "CAPTCHA" not in html:
        return False
    if soup is None:
        return False
    return "CAPTCHA" in (soup.text(deep=True) or "")


def get_link_list(soup: Node | None) -> list[str] | None:
    """All descendant anchor ``href``s in document order; ``None`` when none."""
    if soup is None:
        return None
    out = [str(a.attrs["href"]) for a in soup.css("a") if a.attrs.get("href") and has_text(a)]
    return out or None


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
    if domain.subdomain and domain.subdomain != "www":
        return ".".join([domain.subdomain, domain.domain, domain.suffix])
    return ".".join([domain.domain, domain.suffix])


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
