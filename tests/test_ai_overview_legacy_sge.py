"""Test AI Overview extraction on legacy (2024-era) SGE markup.

The current-DOM ``ai_overview`` parser targets classes absent from 2024 SGE
captures; ``parse_ai_overview`` falls back to legacy extractors when the current
body container (``div.mZJni``) is missing. These captures are detected as
``ai_overview`` but historically yielded empty output. Content-bearing overviews
must now recover their answer text + sources; genuine "Can't generate an AI
overview right now" failures must stay empty.
"""

import bz2
from pathlib import Path

import orjson
import pytest

import WebSearcher as ws

FIXTURE = Path(__file__).parent / "fixtures" / "serps-sge-2024.json.bz2"

# qry -> whether the overview carries recoverable content (vs a genuine failure)
CONTENT_QRYS = {
    "my work is done why wait",
    "metropolitan los angeles area",
    "barclays job cuts",
    "cancer deaths per year in the usa",  # flat (no sections)
    "problems with bible translations",  # multi-section
}
FAILURE_QRYS = {
    "tesla manifesto",
    "honeywell c level management figures",
}


def _load():
    with bz2.open(FIXTURE, "rt") as f:
        return [orjson.loads(line) for line in f]


@pytest.fixture(scope="module")
def serps_by_qry():
    if not FIXTURE.exists():
        pytest.skip("legacy SGE fixture not available")
    return {r["qry"]: r for r in _load()}


def _ai_overview_rows(html):
    return [r for r in ws.parse_serp(html)["results"] if r["type"] == "ai_overview"]


@pytest.mark.parametrize("qry", sorted(CONTENT_QRYS))
def test_legacy_sge_recovers_content(serps_by_qry, qry):
    rows = _ai_overview_rows(serps_by_qry[qry]["html"])
    assert len(rows) == 1
    row = rows[0]
    # lede answer text recovered
    assert row["text"] and len(row["text"]) > 50
    details = row["details"]
    assert details is not None and details["type"] == "ai_overview"
    # sources recovered from the legacy tray with url + title + publisher
    sources = details.get("sources") or []
    assert sources, f"{qry}: no sources recovered"
    for src in sources:
        assert src["url"] and src["url"] != "#"
        assert src["title"]
        assert src["publisher"]


def test_legacy_sge_layouts(serps_by_qry):
    """Flat (no heading) and multi-section legacy overviews both parse."""
    flat = _ai_overview_rows(serps_by_qry["cancer deaths per year in the usa"]["html"])[0]
    assert flat["sub_type"] == "flat"
    assert flat["text"]
    assert not (flat["details"] or {}).get("sections")

    multi = _ai_overview_rows(serps_by_qry["problems with bible translations"]["html"])[0]
    assert multi["sub_type"] == "sectioned"
    sections = multi["details"]["sections"]
    assert len(sections) >= 2
    assert all(s["heading"] for s in sections)


@pytest.mark.parametrize("qry", sorted(FAILURE_QRYS))
def test_legacy_sge_failures_stay_empty(serps_by_qry, qry):
    rows = _ai_overview_rows(serps_by_qry[qry]["html"])
    assert len(rows) == 1
    row = rows[0]
    # "Can't generate" panels carry no body/sources -> empty, not hollow
    assert row["text"] is None
    assert row["details"] is None
    # the decline is recorded explicitly, distinct from a parser miss
    assert row["sub_type"] == "unavailable"
