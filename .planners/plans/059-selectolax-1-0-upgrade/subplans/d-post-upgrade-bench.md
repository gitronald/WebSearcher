---
status: done
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

- **2026-10-14T21:50:53-07:00** — Done. selectolax 1.0.0 (`0.11.7a2`, A, `.worktrees/selectolax-1-0-upgrade` at `771c854`) vs 0.4.13 (`0.11.7a1`, B, detached `.worktrees/selectolax-baseline` at `39a5f33`), one session, order A B B A, `--iterations 50 --runs 5`, 102 SERPs, Python 3.14.8. The runs started after c's code was final (`771c854`) and before c was marked done; c's CI was confirmed green while they ran.
  - A1 `20261015T042259Z_771c854`: corpus_total_median_ms 827.5, noise_floor_pct 0.52
  - B1 `20261015T042639Z_39a5f33`: 1565.3, 0.90
  - B2 `20261015T043326Z_39a5f33`: 1573.1, 1.22 (`git_dirty: true` from B1's appended row)
  - A2 `20261015T044013Z_771c854`: 828.4, 0.94 (`git_dirty: true` from A1's appended row)
  - Session check: A-to-A +0.1%, B-to-B +0.5%, both inside their noise floors, so no rerun.
  - A vs B: 828.0 vs 1569.2 ms (means of the pairs), -741 ms, **-47.2%**, about 50x the widest noise floor (1.22%). Per-SERP median 6.7-6.8 ms vs 12.8-13.3 ms.
  - Profiles back to back, 20 iterations: A `20261015T044407Z_771c854` 24.20 s, B `20261015T044435Z_39a5f33` 39.60 s, identical call counts (25,369,181), so the same code paths ran. tottime A vs B:
    - `_slx.py:85(make_soup)` 4.392 vs 9.584 s (lexbor parsing, 2.2x)
    - `classifiers/main.py:55(__init__)` 2.496 vs 4.198 s (CSS probes)
    - `_slx.py:47(_iter_text_fragments)` 1.317 vs 1.786 s
    - `extractors/__init__.py:34(_get_dom_positions)` 1.154 vs 1.566 s
    - `_slx.py:188(subtree_css)` 0.622 vs 1.295 s
    - `_slx.py:100(get_text)` 0.577 vs 1.214 s
    - `extractor_main.py:621(is_valid)` 0.412 vs 0.866 s
    - `classifiers/main.py:115(_classify_header)` 0.445 vs 0.952 s
    - `utils.py:107(has_captcha)` 0.982 vs 0.995 s (one whole-document `text()`: unchanged, so the "5x text" note is not where the win comes from)
    - `_ai_overview_payloads.py:62(_iter_payload_blobs)` 0.896 vs 0.913 s (pure-Python regex: unchanged, a control for machine drift)
  - The gain comes from parsing and CSS matching, which b had classed as lexbor-update `watch` items rather than predicted. b's ~10% ceiling for the `text()` change was right; the rest came from elsewhere.
  - Output checks: full suite on A, 644 passed, 102 snapshots byte-identical (c). Watch types present in the snapshots and unchanged: ad 52 rows, shopping_ads 53, knowledge_rhs 3, notice 18 (2,583 rows, 36 types). `attrs` qualified names: no change in any snapshot. No before/after section needed in the PR.
  - Rows: all six (4 benchmark, 2 profile) committed in `tests/benchmarks/results.jsonl` (`6ee3fe3`); B's rows copied from the baseline tree, which was then removed (`git worktree remove`; no hook pointed into it). Both `.prof` files sit in the gitignored `tests/benchmarks/profiles/`.
  - Deviation: d's done-when asks for the per-step effects in the umbrella's Retrospective. They are in the umbrella Log and Handoff instead, for `/planners close` to carry into the Retrospective it writes.
