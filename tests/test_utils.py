"""Tests for utility functions"""

import hashlib
from pathlib import Path

from selectolax.lexbor import LexborNode as Node

from WebSearcher import utils

# hash_id ----------------------------------------------------------------------


def test_hash_id_produces_sha224():
    expected = hashlib.sha224(b"hello").hexdigest()
    assert utils.hash_id("hello") == expected


def test_hash_id_different_inputs_differ():
    assert utils.hash_id("a") != utils.hash_id("b")


# get_between_parentheses -----------------------------------------------------


def test_get_between_parentheses():
    assert utils.get_between_parentheses("rating (123)") == "123"


def test_get_between_parentheses_first_match():
    assert utils.get_between_parentheses("(first) (second)") == "first"


def test_get_between_parentheses_no_match():
    assert utils.get_between_parentheses("no parens here") == ""


# make_soup --------------------------------------------------------------------


def test_make_soup_from_string():
    soup = utils.make_soup("<html><body><p>hello</p></body></html>")
    assert isinstance(soup, Node)
    assert soup.css_first("p").text(deep=True) == "hello"


def test_make_soup_from_bytes():
    soup = utils.make_soup(b"<html><body><p>bytes</p></body></html>")
    assert soup.css_first("p").text(deep=True) == "bytes"


def test_make_soup_passthrough():
    original = utils.make_soup("<p>test</p>")
    result = utils.make_soup(original)
    assert result is original


# has_captcha ------------------------------------------------------------------


def test_has_captcha_true():
    soup = utils.make_soup("<html><body>Please solve this CAPTCHA</body></html>")
    assert utils.has_captcha(soup) is True


def test_has_captcha_false():
    soup = utils.make_soup("<html><body>Normal search results</body></html>")
    assert utils.has_captcha(soup) is False


def test_has_captcha_sorry_fixture():
    soup = utils.load_soup(Path(__file__).parent / "fixtures" / "sorry_index.html")
    assert utils.has_captcha(soup) is True


# is_sorry_redirect ------------------------------------------------------------

SORRY_URL = (
    "https://www.google.com/sorry/index?continue="
    "https://www.google.com/search%3Fq%3Dwhy%2Bis%2Bthe%2Bsky%2Bblue&q=REDACTED_TOKEN"
)


def test_is_sorry_redirect_true():
    assert utils.is_sorry_redirect(SORRY_URL) is True


def test_is_sorry_redirect_no_www():
    assert utils.is_sorry_redirect("http://google.com/sorry/index?q=abc") is True


def test_is_sorry_redirect_cctld():
    assert utils.is_sorry_redirect("https://www.google.co.uk/sorry/index?q=abc") is True


def test_is_sorry_redirect_other_subdomain():
    assert utils.is_sorry_redirect("https://ipv4.google.com/sorry/index?q=abc") is True


def test_is_sorry_redirect_bare_sorry_path():
    assert utils.is_sorry_redirect("https://www.google.com/sorry?continue=x") is True


def test_is_sorry_redirect_path_prefix_only():
    assert utils.is_sorry_redirect("https://www.google.com/sorrytown") is False


def test_is_sorry_redirect_google_as_subdomain_of_other_domain():
    assert utils.is_sorry_redirect("https://google.example.com/sorry/") is False


def test_is_sorry_redirect_normal_search():
    assert utils.is_sorry_redirect("https://www.google.com/search?q=test") is False


def test_is_sorry_redirect_not_anchored_elsewhere():
    assert utils.is_sorry_redirect("https://example.com/?u=https://www.google.com/sorry/") is False


def test_is_sorry_redirect_empty_or_none():
    assert utils.is_sorry_redirect("") is False
    assert utils.is_sorry_redirect(None) is False


# get_link_list ----------------------------------------------------------------


def test_get_link_list():
    soup = utils.make_soup('<div><a href="/a">1</a><a href="/b">2</a></div>')
    links = utils.get_link_list(soup)
    assert links == ["/a", "/b"]


def test_get_link_list_none_soup():
    assert utils.get_link_list(None) is None


# URL functions ----------------------------------------------------------------


def test_encode_param_value():
    assert utils.encode_param_value("hello world") == "hello+world"
    assert utils.encode_param_value("a&b=c") == "a%26b%3Dc"


def test_url_unquote():
    assert utils.url_unquote("hello%20world") == "hello world"
    assert utils.url_unquote("a%26b") == "a&b"


def test_join_url_quote():
    result = utils.join_url_quote({"q": "hello+world", "hl": "en"})
    assert result == "q=hello+world&hl=en"


def test_get_domain_basic():
    assert utils.get_domain("https://www.example.com/page") == "example.com"


def test_get_domain_with_subdomain():
    assert utils.get_domain("https://blog.example.com/page") == "blog.example.com"


def test_get_domain_none():
    assert utils.get_domain(None) == ""


def test_get_domain_empty():
    assert utils.get_domain("") == ""


# read_lines / write_lines ----------------------------------------------------


def test_write_and_read_json(tmp_path):
    fp = tmp_path / "data.json"
    data = [{"key": "value", "num": 42}, {"key": "other", "num": 7}]
    utils.write_lines(data, fp)
    result = utils.read_lines(fp)
    assert result == data


def test_write_and_read_text(tmp_path):
    fp = tmp_path / "data.txt"
    lines = ["line one", "line two", "line three"]
    utils.write_lines(lines, fp)
    result = utils.read_lines(fp)
    assert result == lines


def test_write_lines_append(tmp_path):
    fp = tmp_path / "data.json"
    utils.write_lines([{"a": 1}], fp)
    utils.write_lines([{"b": 2}], fp)
    result = utils.read_lines(fp)
    assert len(result) == 2
    assert result[0] == {"a": 1}
    assert result[1] == {"b": 2}


def test_write_lines_overwrite(tmp_path):
    fp = tmp_path / "data.json"
    utils.write_lines([{"a": 1}], fp)
    utils.write_lines([{"b": 2}], fp, overwrite=True)
    result = utils.read_lines(fp)
    assert len(result) == 1
    assert result[0] == {"b": 2}


def test_read_lines_accepts_path_object(tmp_path):
    fp = tmp_path / "test.json"
    utils.write_lines([{"x": 1}], fp)
    result = utils.read_lines(Path(fp))
    assert result == [{"x": 1}]


# load_html / load_soup -------------------------------------------------------


def test_load_html(tmp_path):
    fp = tmp_path / "page.html"
    fp.write_text("<html><body>hello</body></html>")
    content = utils.load_html(fp)
    assert "hello" in content


def test_load_html_brotli(tmp_path):
    import brotli

    fp = tmp_path / "page.html.br"
    original = b"<html><body>compressed</body></html>"
    fp.write_bytes(brotli.compress(original))
    content = utils.load_html(fp, zipped=True)
    assert b"compressed" in content


def test_load_soup(tmp_path):
    fp = tmp_path / "page.html"
    fp.write_text("<html><body><p>soup test</p></body></html>")
    soup = utils.load_soup(fp)
    assert isinstance(soup, Node)
    assert soup.css_first("p").text(deep=True) == "soup test"
