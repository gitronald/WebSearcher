"""Targeted tests for parser-coverage fixes (plan 024).

Each test loads the curated ``serps-parser-coverage.json.bz2`` fixture, whose
SERPs were selected to exercise specific parser gaps. Tests are added per phase
as the fixes land.
"""

import bz2
from pathlib import Path

import orjson
import pytest

import WebSearcher as ws

FIXTURE = Path(__file__).parent / "fixtures" / "serps-parser-coverage.json.bz2"


def _load():
    with bz2.open(FIXTURE, "rt") as f:
        return [orjson.loads(line) for line in f]


@pytest.fixture(scope="module")
def serps_by_qry():
    if not FIXTURE.exists():
        pytest.skip("parser-coverage fixture not available")
    return {r["qry"]: r for r in _load()}


def _rows(html, type_):
    return [r for r in ws.parse_serp(html)["results"] if r["type"] == type_]


# --- recipes (phase 2) -----------------------------------------------------

RECIPE_QRYS = ["birthday cake with candles", "biscuit and gravy recipe"]


@pytest.mark.parametrize("qry", RECIPE_QRYS)
def test_recipes_structured(serps_by_qry, qry):
    rows = _rows(serps_by_qry[qry]["html"], "recipes")
    assert rows, f"{qry}: no recipe cards parsed"
    for r in rows:
        # title + url recovered, no <|>-joined blob, no not-implemented error
        assert r["title"]
        assert r["url"] and r["url"].startswith("http")
        assert "<|>" not in (r["text"] or "")
        assert r["error"] is None
        # structured metadata reusing the ratings details type
        details = r["details"]
        assert details is not None and details["type"] == "ratings"
        assert details.get("source")


# --- knowledge: empty sub_types (phase 3) ----------------------------------


def _knowledge(html, sub_type):
    return [
        r
        for r in ws.parse_serp(html)["results"]
        if r["type"] == "knowledge" and r.get("sub_type") == sub_type
    ]


@pytest.mark.parametrize(
    "qry", ["mater (cars)", "pitbull i believe that we will win (world anthem)"]
)
def test_knowledge_featured_results(serps_by_qry, qry):
    rows = _knowledge(serps_by_qry[qry]["html"], "featured_results")
    assert rows
    # recovers text + an absolute source url (was entirely empty before)
    assert any(r["text"] and r["url"] and r["url"].startswith("http") for r in rows)


@pytest.mark.parametrize("qry", ["cistern", "define judgement"])
def test_knowledge_dictionary(serps_by_qry, qry):
    rows = _knowledge(serps_by_qry[qry]["html"], "dictionary")
    assert rows
    row = rows[0]
    # headword + definition text recovered (was entirely empty before)
    assert row["title"]
    assert row["text"] and len(row["text"]) > 20


@pytest.mark.parametrize("qry", ["prouve", "red skin peanuts", "file folder"])
def test_knowledge_panel_rhs_not_empty(serps_by_qry, qry):
    rows = _knowledge(serps_by_qry[qry]["html"], "panel_rhs")
    assert rows
    for r in rows:
        # no longer a hollow placeholder: has a title and/or text and/or details
        assert r["title"] or r["text"] or r["details"]


def test_knowledge_panel_rhs_entity_title(serps_by_qry):
    """Entity panels recover their title from the data-attrid (was empty)."""
    row = _knowledge(serps_by_qry["prouve"]["html"], "panel_rhs")[0]
    assert row["title"] == "Jean Prouvé"
    assert row["text"] and row["url"]


# --- twitter_cards: legacy card title (phase 4) ----------------------------


@pytest.mark.parametrize("qry", ["movement", "oscar the grouch"])
def test_twitter_card_title_from_handle(serps_by_qry, qry):
    rows = [
        r
        for r in ws.parse_serp(serps_by_qry[qry]["html"])["results"]
        if r["type"] == "twitter_cards" and r.get("sub_type") == "card"
    ]
    assert rows
    for r in rows:
        # single-account carousel: title recovered as the author handle (@...)
        assert r["title"] and r["title"].startswith("@")
        assert r["text"]  # tweet body still extracts
        assert r["url"]


# --- shopping_ads: modern PLA cards (phase 5) ------------------------------


@pytest.mark.parametrize("qry", ["drawing tablet", "kelly kettle"])
def test_shopping_ads_modern_pla(serps_by_qry, qry):
    rows = _rows(serps_by_qry[qry]["html"], "shopping_ads")
    # modern clickable-card layout: multiple products, each with title + url
    assert len(rows) > 1
    for r in rows:
        assert r["title"]
        assert r["url"]
        assert r["error"] is None
        # price/source captured in a ratings details block
        assert r["details"] is None or r["details"]["type"] == "ratings"
