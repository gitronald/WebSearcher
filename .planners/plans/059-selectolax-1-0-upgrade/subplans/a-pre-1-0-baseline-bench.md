---
status: active
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
