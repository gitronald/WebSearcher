"""Integrity guard for the consolidated SERP fixture corpus.

Promotes the assertions from the corpus-curate skill's ``verify_corpus.py`` into the
tracked pytest suite so a clean checkout / CI validates corpus health:

  * serp_ids are unique
  * every record carries a non-empty ``note``
  * every record parses to a non-null ``features.main_layout`` (parser health)
  * every record yields at least one result (no empty parse)

The rich ``--dump`` report lives in the skill; this is just the gate.
"""

import bz2
from collections import Counter
from pathlib import Path

import orjson
import pytest

import WebSearcher as ws

FIXTURE = Path(__file__).parent / "fixtures" / "serps.json.bz2"


def load_records() -> list[dict]:
    with bz2.open(FIXTURE, "rt") as f:
        return [orjson.loads(line) for line in f]


RECORDS = load_records() if FIXTURE.exists() else []


def _label(rec: dict) -> str:
    return rec.get("qry") or rec.get("serp_id", "")[:16] or "?"


@pytest.mark.skipif(not RECORDS, reason="fixture corpus not present")
def test_serp_ids_unique():
    ids = [r["serp_id"] for r in RECORDS]
    dupes = [sid for sid, n in Counter(ids).items() if n > 1]
    assert not dupes, f"duplicate serp_ids: {dupes}"


@pytest.mark.skipif(not RECORDS, reason="fixture corpus not present")
def test_every_record_has_a_note():
    missing = [r["serp_id"][:12] for r in RECORDS if not r.get("note")]
    assert not missing, f"records missing a note: {missing}"


@pytest.mark.skipif(not RECORDS, reason="fixture corpus not present")
@pytest.mark.parametrize("record", RECORDS, ids=_label)
def test_record_yields_layout_and_results(record):
    parsed = ws.parse_serp(record["html"])
    assert parsed["features"].get("main_layout"), f"{_label(record)}: null main_layout"
    assert parsed["results"], f"{_label(record)}: empty parse (no results)"
