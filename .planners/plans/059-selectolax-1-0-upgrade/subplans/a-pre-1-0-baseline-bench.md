---
status: done
branch:
---

# Bump to selectolax 0.4.13 and benchmark the baseline

Part of [Upgrade selectolax to 1.0](../plan.md).

## Plan

Move the lock from selectolax 0.4.10 to 0.4.13, the latest pre-1.0 release, bump
the prerelease to `0.11.7a1`, and record the benchmark that the 1.0.0 upgrade is
measured against.

### Steps

1. Start the plan with `/planners implement 059`: it activates the plan on `dev`,
   creates `feature/selectolax-1-0-upgrade` and its worktree at
   `.worktrees/selectolax-1-0-upgrade`. Run `uv sync --all-groups` in the worktree.
2. Stamp the selectolax version on bench rows (umbrella Handoff question 1,
   answered yes): add it to the row metadata in `WebSearcher/parsers/bench.py`
   and commit it before any benchmark runs, so every row in this effort carries
   it. Update the "Rows do not stamp dependency versions" line in the
   `parse-bench` skill (`.claude/skills/parse-bench/SKILL.md`, gitignored) to
   match.
3. Reference run on the current lock (0.4.10, `0.11.7a0`):

   ```bash
   uv run python -c "import selectolax; print(selectolax.__version__)"   # 0.4.10
   uv run python -m WebSearcher.parsers.bench --iterations 50 --runs 5
   ```

4. Bump the dependency. In `pyproject.toml` set `"selectolax>=0.4.13,<1.0.0"`, then:

   ```bash
   uv lock --upgrade-package selectolax
   uv sync --all-groups
   uv run python -c "import selectolax; print(selectolax.__version__)"   # 0.4.13
   uv run pytest
   ```

   The snapshot suite must pass with no snapshot updates (umbrella decision 5).
   Commit `pyproject.toml` and `uv.lock`.
5. Bump the prerelease: `stanza release prerelease -y` (`0.11.7a0 -> 0.11.7a1`).
   Push the branch first and keep it level with origin
   (`git push -u origin feature/selectolax-1-0-upgrade`): stanza's preflight
   fails on a branch origin does not have, and it pushes the bump itself
   (umbrella Handoff question 2).
   Confirm `uv run python -c "import WebSearcher; print(WebSearcher.__version__)"`.
6. Baseline runs on 0.4.13 (`0.11.7a1`), in the same session as step 3:

   ```bash
   uv run python -m WebSearcher.parsers.bench --iterations 50 --runs 5
   uv run python -m WebSearcher.parsers.bench --profile --iterations 20
   ```

   The profile's `.prof` lands in the gitignored `tests/benchmarks/profiles/`; its
   top frames go in the Log so d can compare them without the file.
7. Commit the new `tests/benchmarks/results.jsonl` rows.

### Done when

- `uv.lock` resolves selectolax 0.4.13 and the version reads `0.11.7a1`.
- The full suite passes with no snapshot changes.
- The Log records, for the 0.4.10 and 0.4.13 rows: row ids,
  `corpus_total_median_ms`, `noise_floor_pct`, the delta between them and whether
  it clears the noise floor, and the top ten `tottime` frames of the 0.4.13
  profile.

The 0.4.10 -> 0.4.13 delta is an aside. The 0.4.13 rows are the reference for d,
which still re-runs 0.4.13 in its own session (umbrella decision 4).

## Log

- **2026-10-14T21:18:24-07:00** — Done. 0.4.10 -> 0.4.13, `0.11.7a0 -> 0.11.7a1`, bench rows stamp `selectolax_version`.
  - Commits: `1131ea9` stamp selectolax version on bench rows; `2d66619` collect gc after each timed serp in bench; `3fbeca5` bump selectolax to 0.4.13 (`>=0.4.13,<1.0.0`); `667664a` 0.4.10 row; `39a5f33` stanza `version [prerelease]: 0.11.7a1`; `dc18beb` 0.4.13 rows.
  - Suite on 0.4.13: 644 passed, 102 snapshots passed, no updates.
  - Bench fix, found on the way: the first two 0.4.10 runs (50x5) are void. One exited with an empty log (stdout was block-buffered, so nothing survived); the re-run with `PYTHONUNBUFFERED=1` printed runs 1-4 and exited 137 (SIGKILL). Peak RSS grew with iterations (`/usr/bin/time -v ... --iterations N --runs 1 --no-save`: 1.0 GB at N=1, 3.2 GB at N=5, 6.0 GB at N=10), about 5.5 MB per parse, so a 50x5 run needs well over the machine's memory. `parse_serp` itself does not leak (+0.003 MB/call with `gc.collect()` between batches); each parse leaves reference cycles holding its tree (6555 objects freed by one `gc.collect()` after 50 parses), and `time_parse` ran with gc disabled and never collected. Fix: `gc.collect()` after `gc.enable()` in `time_parse`, outside the timed region. Peak RSS is now flat (0.51 GB at N=1, 0.54 GB at N=10) and timings dropped about 10-15% at the same commit, so earlier rows in `results.jsonl` were measured under heap growth and are not comparable with rows from this effort.
  - 0.4.10 (`0.11.7a0`) row `20261015T040256Z_2d66619`: corpus_total_median_ms 1556.9, noise_floor_pct 0.28.
  - 0.4.13 (`0.11.7a1`) row `20261015T041031Z_39a5f33`: corpus_total_median_ms 1571.2, noise_floor_pct 0.84.
  - Delta 0.4.10 -> 0.4.13: +14.3 ms (+0.92%), at the edge of the wider noise floor (0.84%); the two runs were about 8 minutes apart, so treat it as no measurable change.
  - 0.4.13 profile row `20261015T041716Z_39a5f33` (20 iterations, 39.2 s, `git_dirty: true` only because the bench row had just been appended). Top ten by tottime:
    - `_slx.py:85(make_soup)` 2040 calls, 9.486 s
    - `main.py:55(__init__)` 26120, 4.169 s
    - `_slx.py:47(_iter_text_fragments)` 524520, 1.786 s
    - `__init__.py:34(_get_dom_positions)` 2040, 1.529 s
    - `_slx.py:188(subtree_css)` 19000, 1.284 s
    - `extractor_serp_features.py:95(_extract_from_html)` 2040, 1.254 s
    - `_slx.py:100(get_text)` 342280, 1.205 s
    - `utils.py:107(has_captcha)` 2040, 0.988 s
    - `main.py:115(_classify_header)` 44720, 0.946 s
    - `_ai_overview_payloads.py:62(_iter_payload_blobs)` 62980, 0.894 s
  - Skill: the `parse-bench` skill's "Rows do not stamp dependency versions" line now says rows stamp `selectolax_version` (gitignored file, edited in the main checkout and the worktree copy).
