---
status: done
branch: dev
created: 2026-02-22T12:56:12-08:00
completed: 2026-02-06T11:18:08-08:00
pr: https://github.com/gitronald/WebSearcher/pull/94
---

# Add compressed test fixtures for CI

## Context

The test suite depends on demo SERP data in `data/` (gitignored) and syrupy snapshots in `tests/__snapshots__/` (untracked). The new CI test workflow skips all tests because this data isn't in the repo.

Prerelease demo data accumulates across directories (`data/demo-ws-v0.6.7a{0,2,3,4}/`), totaling 10 unique SERPs and 16MB raw. Combining per major version into a single bz2-compressed file reduces this to ~3.2MB.

## Plan

### 1. Add condense script: `scripts/condense_fixtures.py`

Typer CLI (matches existing script conventions) that:
- Takes a version string (e.g. `0.6.7`)
- Globs `data/demo-ws-v{version}*/serps.json`
- Deduplicates records by `serp_id`
- Writes `tests/fixtures/serps-v{version}.json.bz2`
- Prints summary (records found, deduplicated, output size)

```bash
poetry run python scripts/condense_fixtures.py 0.6.7
```

### 2. Generate the fixture

Run the script to create `tests/fixtures/serps-v0.6.7.json.bz2` (~3.2MB).

### 3. Update tests: `tests/test_parse_serp.py`

- Replace `DATA_DIR`/`SERPS_PATH` with fixture path
- Add `import bz2`
- Update `load_serps()` to use `bz2.open`

```python
import bz2

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SERPS_PATH = FIXTURES_DIR / "serps-v0.6.7.json.bz2"

def load_serps(path: Path) -> list[dict]:
    """Load SERP records from a bz2-compressed JSON-lines file"""
    with bz2.open(path, "rt") as f:
        return [json.loads(line) for line in f]
```

### 4. Regenerate snapshots

New SERPs (6 additional) need snapshot baselines:

```bash
poetry run pytest tests/ --snapshot-update
```

### 5. Commit

- `scripts/condense_fixtures.py` (new)
- `tests/fixtures/serps-v0.6.7.json.bz2` (new, ~3.2MB)
- `tests/test_parse_serp.py` (modified)
- `tests/__snapshots__/` (new/updated)

## Workflow going forward

1. Collect demo SERPs during prerelease development → `data/demo-ws-v{prerelease}/`
2. Run `poetry run python scripts/condense_fixtures.py {version}` to update the fixture
3. Run `poetry run pytest tests/ --snapshot-update` if new SERPs were added
4. Commit updated fixture and snapshots

## Verification

```bash
poetry run pytest tests/ -q
```
