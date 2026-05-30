"""Pinning tests for the knowledge-panel sub_type dispatch (plan 028 phase 2).

The wide-format knowledge panel routes ~13 sub_types through an ordered
detector cascade. Several of those sub_types (``featured_snippet``, ``finance``,
``calculator``, ``election``) appear in no SERP fixture, and two branches are
*conditional consumers* whose subtle behavior is easy to regress:

- ``things_to_know`` matches on a heading span's presence but only assigns a
  sub_type when the heading text is in the known set -- otherwise the row is
  emitted with **no** ``sub_type`` key.
- the dynamic ``slugify`` branch requires *both* ``div.JNkvid`` and a level-2
  section heading; with the former but not the latter it falls through to
  ``panel``.

These tests pin that behavior with minimal synthetic markup (detector-only
branches) and against the curated coverage fixture (dynamic slug branch), so the
table-driven refactor stays output-preserving.
"""

import bz2
from pathlib import Path

import orjson
import pytest

import WebSearcher as ws
from WebSearcher._slx import make_soup
from WebSearcher.component_parsers.knowledge import parse_knowledge_panel

FIXTURE = Path(__file__).parent / "fixtures" / "serps-parser-coverage.json.bz2"


def _sub_type(html):
    """Parse a knowledge-panel HTML fragment and return the single row.

    Production calls ``parse_knowledge_panel`` with the component root
    (``div.kp-blk``), not the document root, so select that node to mirror real
    usage and avoid matches leaking outside the panel as fragments grow.
    """
    return parse_knowledge_panel(make_soup(html).css_first("div.kp-blk"))[0]


# --- detector-only branches (synthetic markup) -----------------------------

DETECTOR_CASES = {
    "featured_snippet_h2": (
        '<div class="kp-blk"><h2>Featured snippet from the web</h2><span>An answer.</span></div>',
        "featured_snippet",
    ),
    "featured_snippet_answered_question": (
        '<div class="kp-blk"><div class="answered-question"><span>Yes.</span></div></div>',
        "featured_snippet",
    ),
    "unit_converter": (
        '<div class="kp-blk"><h2>Unit Converter</h2><span>1 m = 100 cm</span></div>',
        "unit_converter",
    ),
    "sports": (
        '<div class="kp-blk"><h2>Sports Results</h2><div class="SwsxUd">Final 3-1</div></div>',
        "sports",
    ),
    "weather": (
        '<div class="kp-blk"><h2>Weather Result</h2><span>72F</span></div>',
        "weather",
    ),
    "finance_h2": (
        '<div class="kp-blk"><h2>Finance Results</h2><span>AAPL</span></div>',
        "finance",
    ),
    "finance_entity_summary_div": (
        '<div class="kp-blk"><div id="knowledge-finance-wholepage__entity-summary">'
        "<span>AAPL</span></div></div>",
        "finance",
    ),
    "calculator": (
        '<div class="kp-blk"><h2>Calculator Result</h2><span>2 + 2 = 4</span></div>',
        "calculator",
    ),
    "translate": (
        '<div class="kp-blk"><h2>Translation Result</h2><span>hola</span></div>',
        "translate",
    ),
    "election": (
        '<div class="kp-blk"><div role="heading">2020 US election results</div>'
        "<span>results</span></div>",
        "election",
    ),
}


@pytest.mark.parametrize("html,expected", DETECTOR_CASES.values(), ids=list(DETECTOR_CASES))
def test_knowledge_detector_sub_type(html, expected):
    assert _sub_type(html)["sub_type"] == expected


# --- conditional-consumer edge cases ---------------------------------------


def test_things_to_know_match_sets_sub_type():
    html = '<div class="kp-blk"><span role="heading" class="IFnjPb">Things to know</span></div>'
    row = _sub_type(html)
    assert row["sub_type"] == "things_to_know"
    assert row["details"]["heading"] == "Things to know"


def test_things_to_know_nonmatch_leaves_no_sub_type():
    # heading span present but text not in the known set: the branch is consumed
    # and NO sub_type key is set (must not fall through to the panel branch).
    html = '<div class="kp-blk"><span role="heading" class="IFnjPb">Other heading</span></div>'
    row = _sub_type(html)
    assert "sub_type" not in row


def test_jnkvid_without_section_heading_falls_to_panel():
    html = '<div class="kp-blk"><div class="JNkvid"><div>x</div></div></div>'
    assert _sub_type(html)["sub_type"] == "panel"


def test_jnkvid_with_section_heading_slugifies():
    html = (
        '<div class="kp-blk"><div class="JNkvid"></div>'
        '<div role="heading" aria-level="2">Cast & Crew</div>'
        '<div role="heading" aria-level="3">An Actor</div></div>'
    )
    row = _sub_type(html)
    # slugify(lower) then map the literal "&" token to "and"
    assert row["sub_type"] == "cast-and-crew"
    assert row["title"] == "Cast & Crew"
    assert row["details"]["items"] == ["An Actor"]


# --- dynamic slug branch from the real coverage fixture --------------------


@pytest.fixture(scope="module")
def serps_by_qry():
    if not FIXTURE.exists():
        pytest.skip("parser-coverage fixture not available")
    with bz2.open(FIXTURE, "rt") as f:
        return {r["qry"]: r for r in (orjson.loads(line) for line in f)}


@pytest.mark.parametrize(
    "qry,sub_type",
    [
        ("oscar the grouch", "played-by"),
        ("oscar the grouch", "songs"),
        ("mater (cars)", "movies"),
        ("pitbull i believe that we will win (world anthem)", "lyrics"),
    ],
)
def test_knowledge_dynamic_slug_sub_types(serps_by_qry, qry, sub_type):
    rows = [
        r
        for r in ws.parse_serp(serps_by_qry[qry]["html"])["results"]
        if r["type"] == "knowledge" and r.get("sub_type") == sub_type
    ]
    assert rows, f"{qry}: expected a knowledge row with sub_type={sub_type!r}"
    assert rows[0]["title"]
