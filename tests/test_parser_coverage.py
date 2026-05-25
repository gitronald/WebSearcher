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
