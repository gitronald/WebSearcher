"""Tests for utility functions"""

import hashlib
from pathlib import Path

from bs4 import BeautifulSoup

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


# check_dict_value -------------------------------------------------------------


def test_check_dict_value_match():
    assert utils.check_dict_value({"role": "complementary"}, "role", "complementary") is True


def test_check_dict_value_mismatch():
    assert utils.check_dict_value({"role": "main"}, "role", "complementary") is False


def test_check_dict_value_missing_key():
    assert utils.check_dict_value({"other": "val"}, "role", "complementary") is False


def test_check_dict_value_list():
    assert utils.check_dict_value({"class": ["a", "b"]}, "class", ["a", "b"]) is True


# make_soup --------------------------------------------------------------------


def test_make_soup_from_string():
    soup = utils.make_soup("<html><body><p>hello</p></body></html>")
    assert isinstance(soup, BeautifulSoup)
    assert soup.find("p").text == "hello"


def test_make_soup_from_bytes():
    soup = utils.make_soup(b"<html><body><p>bytes</p></body></html>")
    assert soup.find("p").text == "bytes"


def test_make_soup_passthrough():
    original = BeautifulSoup("<p>test</p>", "lxml")
    result = utils.make_soup(original)
    assert result is original


# has_captcha ------------------------------------------------------------------


def test_has_captcha_true():
    soup = utils.make_soup("<html><body>Please solve this CAPTCHA</body></html>")
    assert utils.has_captcha(soup) is True


def test_has_captcha_false():
    soup = utils.make_soup("<html><body>Normal search results</body></html>")
    assert utils.has_captcha(soup) is False


# get_div / get_text / get_link ------------------------------------------------


def test_get_div_finds_element():
    soup = utils.make_soup("<div><span class='x'>hi</span></div>")
    div = utils.get_div(soup, "span", {"class": "x"})
    assert div.text == "hi"


def test_get_div_none_soup():
    assert utils.get_div(None, "div") is None


def test_get_div_no_match():
    soup = utils.make_soup("<div>hello</div>")
    assert utils.get_div(soup, "span") is None


def test_get_text_basic():
    soup = utils.make_soup("<div><h3>Title</h3></div>")
    assert utils.get_text(soup, "h3") == "Title"


def test_get_text_strip():
    soup = utils.make_soup("<div>  spaced  </div>")
    assert utils.get_text(soup, strip=True) == "spaced"
    assert utils.get_text(soup, strip=False) == "  spaced  "


def test_get_text_none_soup():
    assert utils.get_text(None, "h3") is None


def test_get_text_no_match():
    soup = utils.make_soup("<div>hello</div>")
    assert utils.get_text(soup, "h3") is None


def test_get_text_separator():
    soup = utils.make_soup("<div><p>a</p><p>b</p></div>")
    result = utils.get_text(soup, "div", separator="<|>")
    assert "<|>" in result


def test_get_link_basic():
    soup = utils.make_soup('<div><a href="https://example.com">link</a></div>')
    assert utils.get_link(soup) == "https://example.com"


def test_get_link_none_soup():
    assert utils.get_link(None) is None


def test_get_link_no_anchor():
    soup = utils.make_soup("<div>no link</div>")
    assert utils.get_link(soup) is None


def test_get_link_with_attrs():
    soup = utils.make_soup(
        '<div><a class="other" href="/other">x</a><a class="target" href="/found">y</a></div>'
    )
    assert utils.get_link(soup, {"class": "target"}) == "/found"


# get_link_list ----------------------------------------------------------------


def test_get_link_list():
    soup = utils.make_soup('<div><a href="/a">1</a><a href="/b">2</a></div>')
    links = utils.get_link_list(soup)
    assert links == ["/a", "/b"]


def test_get_link_list_none_soup():
    assert utils.get_link_list(None) is None


# get_text_by_selectors --------------------------------------------------------


def test_get_text_by_selectors_first_match():
    soup = utils.make_soup('<div><span class="a">first</span><span class="b">second</span></div>')
    selectors = [("span", {"class": "a"}), ("span", {"class": "b"})]
    assert utils.get_text_by_selectors(soup, selectors) == "first"


def test_get_text_by_selectors_fallback():
    soup = utils.make_soup('<div><span class="b">fallback</span></div>')
    selectors = [("span", {"class": "a"}), ("span", {"class": "b"})]
    assert utils.get_text_by_selectors(soup, selectors) == "fallback"


def test_get_text_by_selectors_none():
    assert utils.get_text_by_selectors(None, [("div", {})]) is None
    soup = utils.make_soup("<div>hi</div>")
    assert utils.get_text_by_selectors(soup, None) is None


# find_all_divs ----------------------------------------------------------------


def test_find_all_divs():
    soup = utils.make_soup("<div><p>a</p><p>b</p><p> </p></div>")
    divs = utils.find_all_divs(soup, "p")
    assert len(divs) == 2  # empty one filtered


def test_find_all_divs_no_filter():
    soup = utils.make_soup("<div><p>a</p><p> </p></div>")
    divs = utils.find_all_divs(soup, "p", filter_empty=False)
    assert len(divs) == 2


def test_find_all_divs_none_soup():
    assert utils.find_all_divs(None, "div") == []


# filter_empty_divs ------------------------------------------------------------


def test_filter_empty_divs():
    soup = utils.make_soup("<div><p>content</p><p>  </p><p>more</p></div>")
    all_p = soup.find_all("p")
    filtered = utils.filter_empty_divs(all_p)
    assert len(filtered) == 2


# find_children ----------------------------------------------------------------


def test_find_children():
    soup = utils.make_soup('<div class="parent"><span>a</span><span>b</span></div>')
    children = list(utils.find_children(soup, "div", {"class": "parent"}))
    assert len(children) >= 2


def test_find_children_no_match():
    soup = utils.make_soup("<div>hello</div>")
    children = list(utils.find_children(soup, "span"))
    assert children == []


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
    assert isinstance(soup, BeautifulSoup)
    assert soup.find("p").text == "soup test"
