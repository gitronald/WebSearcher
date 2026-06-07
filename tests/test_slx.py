"""Tests for native selectolax helpers in WebSearcher._slx."""

from selectolax.lexbor import LexborHTMLParser

from WebSearcher._slx import is_hidden


def _first(html: str, css: str):
    return LexborHTMLParser(html).css_first(css)


# is_hidden --------------------------------------------------------------------


def test_is_hidden_no_style_is_visible():
    node = _first("<div><span id='t'>hi</span></div>", "#t")
    assert is_hidden(node) is False


def test_is_hidden_display_none_with_space():
    node = _first("<div id='t' style='display: none'>hi</div>", "#t")
    assert is_hidden(node) is True


def test_is_hidden_grandparent_hidden():
    html = "<div style='display:none'><section><span id='t'>hi</span></section></div>"
    node = _first(html, "#t")
    assert is_hidden(node) is True


def test_is_hidden_visibility_hidden_still_visible():
    # visibility:hidden is out of scope -- only display:none counts.
    node = _first("<div id='t' style='display: block; visibility: hidden'>hi</div>", "#t")
    assert is_hidden(node) is False


def test_is_hidden_none_is_visible():
    assert is_hidden(None) is False
