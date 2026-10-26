"""Unit tests for the shared component-parser helpers in ``_common`` and the
AI-overview document-order sort, introduced when per-module copies were merged."""

from WebSearcher._slx import make_soup
from WebSearcher.parsers.components import _common
from WebSearcher.parsers.components.ai_overview import _in_document_order


def _node(html: str, css: str):
    node = make_soup(html).css_first(css)
    assert node is not None
    return node


def test_first_text_strips_and_returns_none_when_missing_or_blank():
    card = _node(
        "<div><span class='a'>  Hello <b>there</b> </span><span class='b'>   </span></div>", "div"
    )
    assert _common.first_text(card, "span.a") == "Hello there"
    assert _common.first_text(card, "span.a", sep="") == "Hellothere"
    assert _common.first_text(card, "span.b") is None
    assert _common.first_text(card, "span.missing") is None


def test_under_any_stops_at_the_component_root():
    root = _node("<div id='r'><section id='s'><p id='p'><b id='b'>x</b></p></section></div>", "#r")
    s = root.css_first("#s")
    p = root.css_first("#p")
    b = root.css_first("#b")
    assert s is not None and p is not None and b is not None
    assert _common.under_any(b, {p.mem_id}, root.mem_id) is True
    assert _common.under_any(b, {s.mem_id}, root.mem_id) is True
    assert _common.under_any(b, {root.mem_id}, root.mem_id) is False  # stop_id is exclusive
    assert _common.under_any(p, {b.mem_id}, root.mem_id) is False


def _fact(inner: str) -> tuple[str, str, str | None] | None:
    return _common.parse_lab_fact(_node(f"<div data-attrid='lab/fact/1p/X'>{inner}</div>", "div"))


def test_lab_fact_keeps_the_value_and_records_the_source():
    # The source follows the value; it used to be read as the value.
    assert _fact(
        "<span jsname='BQbCV'>Year</span><div class='TLIZ'><span>1916</span></div>"
        "<div class='KDFsyf'><span>planters.test</span></div>"
    ) == ("Year", "1916", "planters.test")


def test_lab_fact_joins_a_two_line_value_and_a_list():
    assert _fact(
        "<span jsname='BQbCV'>Born</span>"
        "<div class='TLIZ'><span>Mar 14, 1879</span><div>Ulm, Germany</div></div>"
    ) == ("Born", "Mar 14, 1879 · Ulm, Germany", None)
    # An expanded duplicate list beside the value container is not read.
    assert _fact(
        "<span jsname='BQbCV'>Parents</span>"
        "<div class='TLIZ'><span><a>Ann Lee</a>,<a>Bob Lee</a></span></div>"
        "<div><a>Ann Lee</a><a>Bob Lee</a></div>"
    ) == ("Parents", "Ann Lee, Bob Lee", None)


def test_lab_fact_without_label_span_or_value():
    # Rows without the label span take their first fragment as the label.
    assert _fact("<span>Artist</span><div class='TLIZ'>Pitbull</div>") == (
        "Artist",
        "Pitbull",
        None,
    )
    # Without a value container: the fragments after the label, minus the source.
    assert _fact("<span>Year</span><span>1916</span><div class='KDFsyf'>planters.test</div>") == (
        "Year",
        "1916",
        "planters.test",
    )
    assert _fact("<span jsname='BQbCV'>Year</span><div class='TLIZ'></div>") is None


def test_in_document_order_sorts_by_position_in_root():
    root = _node(
        "<div id='r'><p id='a'>1</p><ul id='l'><li id='c'>2</li></ul><p id='b'>3</p></div>", "#r"
    )
    nodes = {n.id: n for n in root.css("[id]") if n.id in {"a", "b", "c", "l"}}
    shuffled = [nodes["b"], nodes["c"], nodes["a"], nodes["l"]]
    assert [n.id for n in _in_document_order(root, shuffled)] == ["a", "l", "c", "b"]
