"""Pinning tests for RHS knowledge-panel fact-row extraction (plan 041).

The complementary kp-wholepage RHS panel carries entity facts on
``data-attrid^="kc:/"`` rows (label + value, e.g. "Director: David Lean"),
which the box pass used to drop entirely. These tests pin the fact pass
(label/value/title resolution, link capture, attrid provenance), the
fact-vs-box dedup, and the corpus-unwitnessed branches (link-less content
boxes, expander-flagged Q&A topics) with synthetic markup.
"""

import bz2
from pathlib import Path

import orjson
import pytest

import WebSearcher as ws
from WebSearcher._slx import make_soup
from WebSearcher.parsers.components.knowledge_rhs import parse_knowledge_rhs

FIXTURE = Path(__file__).parent / "fixtures" / "serps.json.bz2"


@pytest.fixture(scope="module")
def serps_by_qry():
    if not FIXTURE.exists():
        pytest.skip("parser-coverage fixture not available")
    with bz2.open(FIXTURE, "rt") as f:
        return {r["qry"]: r for r in (orjson.loads(line) for line in f)}


def _side_bar(serps_by_qry, qry):
    return [
        r for r in ws.parse_serp(serps_by_qry[qry]["html"])["results"] if r["type"] == "side_bar"
    ]


def _facts(serps_by_qry, qry):
    return [r for r in _side_bar(serps_by_qry, qry) if r.get("sub_type") == "fact"]


# --- labeled facts: label -> title, value -> text, attrid provenance --------


def test_labeled_fact_label_value(serps_by_qry):
    facts = {r["title"]: r for r in _facts(serps_by_qry, "doctor zhivago")}
    director = facts["Director"]
    assert director["text"] == "David Lean"
    assert director["details"]["attrid"] == "kc:/film/film:director"
    assert director["details"]["type"] == "hyperlinks"
    assert director["details"]["items"][0]["text"] == "David Lean"


def test_fact_without_links_is_item_typed(serps_by_qry):
    facts = {r["title"]: r for r in _facts(serps_by_qry, "cngress usa")}
    founded = facts["Founded"]
    assert founded["text"] == "March 4, 1789"
    assert founded["details"] == {
        "type": "item",
        "attrid": "kc:/organization/organization:founded",
    }


def test_local_entity_facts_extracted(serps_by_qry):
    facts = {r["title"]: r for r in _facts(serps_by_qry, "central park new york")}
    assert facts["Address"]["text"] == "New York, NY"
    assert facts["Phone"]["text"] == "(212) 310-6600"
    # the hours table has no LrzXr value span: text falls back to the row text
    assert facts["Hours"]["text"].startswith("Open")
    # unified_actions carries the entity website
    urls = [i["url"] for i in facts["Unified actions"]["details"]["items"]]
    assert "https://www.centralparknyc.org/" in urls


# --- title resolution: exclusive box heading > label > attrid tail ----------


def test_fact_title_from_exclusive_box_heading(serps_by_qry):
    facts = {r["title"]: r for r in _facts(serps_by_qry, "prouve")}
    # the "Structures" box wraps exactly the `designed` fact row
    assert facts["Structures"]["details"]["attrid"] == "kc:/architecture/architect:designed"
    assert len(facts["Structures"]["details"]["items"]) == 4


def test_fact_title_from_attrid_tail(serps_by_qry):
    facts = {r["title"]: r for r in _facts(serps_by_qry, "doctor zhivago")}
    # thumbs_up shares the "About" box with other facts -> humanized tail
    assert facts["Thumbs up"]["details"]["attrid"] == "kc:/ugc:thumbs_up"


def test_survey_headings_never_title_facts(serps_by_qry):
    for r in _side_bar(serps_by_qry, "central park new york"):
        assert not (r["title"] or "").endswith("?")


# --- fact-vs-box dedup ------------------------------------------------------


def test_consumed_box_not_duplicated(serps_by_qry):
    # "Structures" appears once (as the fact row), not also as a links box
    titles = [r["title"] for r in _side_bar(serps_by_qry, "prouve")]
    assert titles.count("Structures") == 1
    assert titles.count("Books") == 1


def test_box_links_exclude_fact_links(serps_by_qry):
    rows = _side_bar(serps_by_qry, "doctor zhivago")
    about = next(r for r in rows if r["title"] == "About")
    about_urls = {i["url"] for i in about["details"]["items"]}
    reviews = next(r for r in rows if r["title"] == "Reviews")
    review_urls = {i["url"] for i in reviews["details"]["items"]}
    assert "https://www.imdb.com/title/tt0059113/" in review_urls
    assert not (about_urls & review_urls)


def test_consumed_box_outside_links_merged(serps_by_qry):
    # the "Watch movie" box holds provider links OUTSIDE the media_actions
    # kc:/ row (the expanded watch list); consuming the box heading must fold
    # them into the fact row, not drop them with the skipped box
    facts = {r["title"]: r for r in _facts(serps_by_qry, "doctor zhivago")}
    urls = {i["url"] for i in facts["Watch movie"]["details"]["items"]}
    assert len(urls) == 4
    assert any("mgmplus.com" in u for u in urls)


def test_edit_affordance_rows_skipped(serps_by_qry):
    attrids = {r["details"]["attrid"] for r in _facts(serps_by_qry, "central park new york")}
    assert "kc:/local:edit info" not in attrids
    assert "kc:/local:pending edits" not in attrids


# --- corpus-unwitnessed branches (synthetic markup) --------------------------


def test_synthetic_labeled_fact():
    html = (
        '<div><div data-attrid="kc:/people/person:born">'
        '<span class="w8qArf">Born :</span>'
        '<span class="LrzXr">April 8, 1901</span></div></div>'
    )
    rows = parse_knowledge_rhs(make_soup(html).css_first("div"))
    assert len(rows) == 1
    assert rows[0]["sub_type"] == "fact"
    assert rows[0]["title"] == "Born"
    assert rows[0]["text"] == "April 8, 1901"
    assert rows[0]["details"] == {"type": "item", "attrid": "kc:/people/person:born"}


def test_synthetic_linkless_box_keeps_title_and_text():
    html = (
        "<div><div>"
        '<div role="heading" aria-level="2"><span>Payment options</span></div>'
        "</div><div>PayPal Apple Pay</div></div>"
    )
    rows = parse_knowledge_rhs(make_soup(html).css_first("div"))
    assert len(rows) == 1
    assert rows[0]["sub_type"] == "links"
    assert rows[0]["title"] == "Payment options"
    assert rows[0]["text"] == "PayPal Apple Pay"
    assert rows[0]["details"] is None


def test_synthetic_expander_topics_without_lab_title():
    # Q&A topic headings flagged only by the iwY1Mb expander span (no
    # lab/title/* attrids): titles fold into the main panel row instead of
    # being dropped with the skipped boxes.
    html = (
        '<div><div role="heading" aria-level="2">'
        '<span>Cost</span><span class="iwY1Mb">&hellip;</span> cost of entry</div>'
        '<div role="heading" aria-level="2">'
        '<span>Secrets</span><span class="iwY1Mb">&hellip;</span> secrets</div></div>'
    )
    rows = parse_knowledge_rhs(make_soup(html).css_first("div"))
    assert len(rows) == 1
    assert rows[0]["sub_type"] == "panel"
    assert rows[0]["title"] == "Things to know"
    assert rows[0]["details"]["items"] == ["Cost", "Secrets"]
