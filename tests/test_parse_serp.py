"""Test SERP parsing pipeline end-to-end"""

import json
from pathlib import Path

import pytest
import WebSearcher as ws
from syrupy.extensions.json import JSONSnapshotExtension


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data" / "demo-ws-v0.6.7a2"
SERPS_PATH = DATA_DIR / "serps.json"


def load_serps(path: Path) -> list[dict]:
    """Load SERP records from a JSON-lines file"""
    records = []
    with open(path) as f:
        for line in f:
            records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)


def pytest_generate_tests(metafunc):
    """Parametrize tests by serp_id from demo data"""
    if "serp_record" not in metafunc.fixturenames:
        return
    if not SERPS_PATH.exists():
        metafunc.parametrize("serp_record", [])
        return
    records = load_serps(SERPS_PATH)
    ids = [r["serp_id"][:12] for r in records]
    metafunc.parametrize("serp_record", records, ids=ids)


# ---------------------------------------------------------------------------
# Snapshot tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not SERPS_PATH.exists(), reason="Demo data not available")
def test_parse_serp(snapshot_json, serp_record):
    """Parse SERP and compare to snapshot"""
    parsed = ws.parse_serp(serp_record["html"], extract_features=True)
    assert parsed == snapshot_json


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------

EXPECTED_KEYS = {
    "section", "cmpt_rank", "sub_rank", "type", "sub_type",
    "title", "url", "text", "cite", "details", "error", "serp_rank",
}


@pytest.fixture(scope="module")
def all_results():
    """Parse all SERPs and collect results"""
    if not SERPS_PATH.exists():
        pytest.skip("Demo data not available")
    results = []
    for record in load_serps(SERPS_PATH):
        parsed = ws.parse_serp(record["html"], extract_features=True)
        results.extend(parsed["results"])
    return results


def test_results_have_expected_keys(all_results):
    """Every result dict has exactly the expected keys"""
    for r in all_results:
        assert set(r.keys()) == EXPECTED_KEYS, f"cmpt {r.get('cmpt_rank')}: {set(r.keys()) ^ EXPECTED_KEYS}"


def test_no_unclassified_results(all_results):
    """No result should have type 'unclassified' (the BaseResult default)"""
    unclassified = [r for r in all_results if r["type"] == "unclassified"]
    assert len(unclassified) == 0


def test_no_unknown_types(all_results):
    """No unknown types after classifier fixes"""
    unknowns = [r for r in all_results if r["type"] == "unknown"]
    assert len(unknowns) == 0, f"Found {len(unknowns)} unknown results"


def test_no_parse_errors(all_results):
    """No parsing errors in results"""
    errors = [r for r in all_results if r["error"] is not None]
    assert len(errors) == 0, f"Found {len(errors)} errors: {[r['error'] for r in errors]}"


def test_general_results_have_title_or_url(all_results):
    """General results without errors should have at least title or url"""
    for r in all_results:
        if r["type"] == "general" and r["error"] is None:
            assert r["title"] is not None or r["url"] is not None, (
                f"cmpt {r['cmpt_rank']} sub {r['sub_rank']}: general result with no title or url"
            )


def test_perspectives_have_url(all_results):
    """Perspectives results should have a url"""
    for r in all_results:
        if r["type"] == "perspectives":
            assert r["url"] is not None, f"perspectives sub {r['sub_rank']}: no url"


def test_serp_rank_is_sequential(all_results):
    """serp_rank values should be sequential from 0"""
    ranks = [r["serp_rank"] for r in all_results]
    assert ranks == list(range(len(ranks)))


def test_field_types(all_results):
    """Validate field types for all results"""
    valid_sections = {"main", "header", "footer", "rhs"}
    for r in all_results:
        assert isinstance(r["section"], str) and r["section"] in valid_sections
        assert isinstance(r["cmpt_rank"], int) and r["cmpt_rank"] >= 0
        assert isinstance(r["serp_rank"], int) and r["serp_rank"] >= 0
        assert isinstance(r["sub_rank"], int) and r["sub_rank"] >= 0
        assert isinstance(r["type"], str)
        assert r["sub_type"] is None or isinstance(r["sub_type"], str)
        assert r["title"] is None or isinstance(r["title"], str)
        assert r["url"] is None or isinstance(r["url"], str)
        assert r["text"] is None or isinstance(r["text"], str)
        assert r["cite"] is None or isinstance(r["cite"], str)
        assert r["error"] is None or isinstance(r["error"], str)
