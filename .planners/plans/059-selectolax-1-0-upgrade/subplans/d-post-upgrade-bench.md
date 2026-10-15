---
status: active
branch:
needs: [c]
---

# Benchmark and verify selectolax 1.0 against the baseline

Part of [Upgrade selectolax to 1.0](../plan.md).

## Plan

Measure 1.0.0 (`0.11.7a2`) against 0.4.13 (`0.11.7a1`) in one session, check the
`watch` items from b, and write up the result for the PR.

### Same-session A/B

The two sides need separate environments at once. Use a second worktree at the
`0.11.7a1` commit (the stanza prerelease commit from a) with its own venv:

```bash
git worktree add --detach .worktrees/selectolax-baseline <a1-commit>
(cd .worktrees/selectolax-baseline && uv sync --all-groups)
```

Then interleave the runs, A = `.worktrees/selectolax-1-0-upgrade` (1.0.0) and
B = `.worktrees/selectolax-baseline` (0.4.13), in the order A B B A:

```bash
uv run python -m WebSearcher.parsers.bench --iterations 50 --runs 5
```

Each tree's bench writes its row to its own `results.jsonl`; copy the B rows into
the branch's file before committing, so both sides are on record.

`make_soup` is not a neutral noise anchor here: it is selectolax parsing, the
thing being changed. The anchor is the repeat of each side instead. If A-to-A or
B-to-B moves by more than the reported noise floor, the session is too noisy;
rerun the whole A B B A sequence rather than trusting the comparison.

Then profile both sides back to back and compare the top `tottime` frames,
particularly `make_soup`, the `_slx` text helpers, and the `attrs` readers b named:

```bash
uv run python -m WebSearcher.parsers.bench --profile --iterations 20
```

Remove the baseline worktree when done: `git worktree remove .worktrees/selectolax-baseline`.

### Output checks

- Full suite, no snapshot updates: `uv run pytest`.
- For each `watch` item from b, show that the component types it names parse the
  same, or document how they differ.
- If any snapshot changed in c, write the PR's before/after section: one or two
  real rows per affected component type, as fenced `diff` blocks of the row dict,
  sourced by diffing the snapshots against the branch's base commit and matching
  rows by `(cmpt_rank, sub_rank)`.

### Done when

- The Log records each run's row id, `corpus_total_median_ms`, and
  `noise_floor_pct`, the A-to-B delta, and whether it clears the noise floor.
- The A and B rows are committed in `tests/benchmarks/results.jsonl`.
- The PR body carries the benchmark result and, if output changed, the
  before/after examples.
- The umbrella's Retrospective notes the measured effect of each step (0.4.10 ->
  0.4.13 from a, 0.4.13 -> 1.0.0 from here).

## Log
