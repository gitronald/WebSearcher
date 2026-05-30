"""Tests for Component dispatch fallbacks: unknown + not-implemented.

These paths are not exercised by the SERP fixtures (every fixture type is
classified to a registered parser), so they are pinned here. Both previously
called a nonexistent ``Node.get_text`` method and would have raised; this
guards the fixed behavior.
"""

from WebSearcher import utils
from WebSearcher.components import Component


def comp(inner: str):
    return utils.make_soup(f'<div class="wrap">{inner}</div>').css_first("div.wrap")


def test_unknown_component_captures_text_without_error():
    c = Component(comp("<span>stray text</span>"), section="main", type="unknown", cmpt_rank=1)
    c.parse_component()
    [result] = c.result_list
    assert result["type"] == "unknown"
    assert result["text"] == "stray text"
    assert result["error"] is None


def test_known_type_without_parser_is_not_implemented():
    # "weather" is a real knowledge sub_type with no standalone registered
    # parser; a component classified directly as an unregistered type falls
    # through to the not-implemented path, keeping its classified type.
    c = Component(comp("<span>widget</span>"), section="main", type="weather", cmpt_rank=2)
    c.parse_component()
    [result] = c.result_list
    assert result["type"] == "weather"
    assert result["text"] == "widget"
    assert result["error"] == "not implemented"


def test_select_parser_returns_none_for_unregistered_type():
    c = Component(comp("<span>x</span>"), section="main", type="weather")
    assert c.select_parser() is None


def test_select_parser_returns_callable_for_unknown_and_registered():
    unknown_c = Component(comp("<span>x</span>"), section="main", type="unknown")
    assert callable(unknown_c.select_parser())
    general_c = Component(comp("<span>x</span>"), section="main", type="general")
    assert callable(general_c.select_parser())
