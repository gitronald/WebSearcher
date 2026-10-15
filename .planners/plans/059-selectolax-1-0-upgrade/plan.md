---
id: 59
slug: selectolax-1-0-upgrade
status: active
branch: feature/selectolax-1-0-upgrade
created: 2026-10-14T20:12:13-07:00
concluded:
pr:
---

# Upgrade selectolax to 1.0

## Plan

### Goal

Move the parser from selectolax 0.4.x to 1.0.0 (released 2026-10-03, notes at
<https://github.com/rushter/selectolax/releases/tag/v1.0.0>), with a measured
performance comparison on each side of the jump and a check of our selectolax
usage against the release's breaking changes. Today `pyproject.toml` declares
`selectolax>=0.4.10` and `uv.lock` resolves 0.4.10; the latest pre-1.0 release
is 0.4.13 (2026-09-29).

### Subplans

<!-- planners:subplans:start -->
| Subplan | Scope | Status | Note |
|---|---|---|---|
| [a](subplans/a-pre-1-0-baseline-bench.md) | Bump to selectolax 0.4.13 and benchmark the baseline | active |  |
| [b](subplans/b-study-1-0-release-notes.md) | Study the selectolax 1.0 release notes for our use | draft |  |
| [c](subplans/c-upgrade-to-1-0.md) | Upgrade selectolax to 1.0 and bump the prerelease | draft |  |
| [d](subplans/d-post-upgrade-bench.md) | Benchmark and verify selectolax 1.0 against the baseline | draft |  |
<!-- planners:subplans:end -->

### Decisions

1. **Two steps, not one.** First move to the latest pre-1.0 release (0.4.13) and
   benchmark it as the baseline; only then move to 1.0.0. That separates the
   0.4.10 -> 0.4.13 delta from the 0.4.13 -> 1.0.0 delta, so a regression or win
   is attributed to the right release.
2. **Bump the prerelease before each benchmark.** Bench rows in
   `tests/benchmarks/results.jsonl` stamp `ws_version` and the git sha but not the
   selectolax version, so the version string is what tells the rows apart:
   0.4.13 runs as `0.11.7a1`, 1.0.0 runs as `0.11.7a2`.
3. **Version strings come from `stanza release prerelease -y`**, which only
   increments the alpha number (`0.11.7a0 -> 0.11.7a1 -> 0.11.7a2`;
   `stanza release prerelease --check --json` on `dev` reports
   `to_version: 0.11.7a1`). stanza has no option to set an explicit version, and
   its preflight requires a prerelease to sort above the latest tag (`v0.11.6`),
   so no `0.11.5.x` or other hand-picked string.
4. **Performance claims come only from same-session A/B runs.** Cross-session
   runs of `WebSearcher.parsers.bench` swing 10-15%, so a row from subplan a is
   not compared with a row from subplan d. Each comparison re-runs both sides
   back to back in one session and gates on the noise floor the bench prints.
5. **Correctness gate: the snapshot suite stays byte-identical.**
   `tests/test_parse_serp.py` runs with no snapshot updates. Any snapshot that
   changes under 1.0.0 is diagnosed against a specific release-note item before
   it is accepted, and recorded with before/after parsed rows.
6. **Bounds.** Step a sets `selectolax>=0.4.13,<1.0.0` so the lock cannot float to
   1.0.0 early; step c replaces it with `selectolax>=1.0.0`.
7. **Adopt only low-risk improvements in this effort.** Subplan b sorts the
   release's changes into "free" (no code change), "adopt now" (small, covered by
   the snapshot suite), and "follow-up" (needs a parser refactor). Subplan c does
   the first two; the third becomes its own plan.
8. **One branch, one PR.** All four steps land on
   `feature/selectolax-1-0-upgrade` and merge to `dev` through a single PR.

### Order

`a -> b -> c -> d`

a and b are independent in principle; they run in this order so b can note
which release items the a baseline should watch.

### Risks

- **Text extraction drift.** 1.0.0 rewrites `text()` (raw-byte concatenation),
  honors `skip_empty` under `deep=True`, and substitutes U+FFFD for undecodable
  bytes on the `deep=False` path. `WebSearcher/_slx.py` wraps both paths
  (`_node_text`, `get_text`), so whitespace or replacement-character changes would
  show up across every component type.
- **Attribute names.** `attrs`/`attributes` now report qualified names
  (`xlink:href` no longer collapses into `href`). Any SVG-bearing card that read
  an `href` this way changes.
- **Tree mutation and iteration.** Fixes to `iter()` during removal, `unwrap()`,
  and `head`/`body` staleness touch helpers that walk or re-parse subtrees
  (`reparse_fragment`, `walk_descendants`, the sibling iterators in `_slx.py`).
- **Downstream consumers** that import selectolax themselves (the Modest
  `selectolax.parser` module is now an `ImportError` stub) break on upgrade
  regardless of what WebSearcher does. The CHANGELOG entry calls this out.
- **Wheel coverage.** CI tests Python 3.12-3.14; confirm 1.0.0 ships wheels for
  each before relying on it.

### Out of scope

- Parser refactors to exploit new 1.0 APIs (for example
  `LexborHTMLParser(..., encoding=True)` for bytes input); b lists them, a
  follow-up plan does them.
- The stable `0.11.7` release itself; this effort ends on `0.11.7a2` merged to
  `dev`.

## Log

- **2026-10-14T20:44:24-07:00** — Activated.
  - Branch: `feature/selectolax-1-0-upgrade`
  - Base: `dev` at `1c7630c`
  - Worktree: `.worktrees/selectolax-1-0-upgrade`
  - PR: pending

## Handoff

Nothing started. Questions:

1. Should `WebSearcher/parsers/bench.py` stamp the installed selectolax version
   on each `results.jsonl` row? It would make rows self-describing instead of
   relying on decision 2. **Answered 2026-10-14: yes.** Subplan a, step 2, adds
   it before any benchmark runs; decision 2 still stands, so rows also differ by
   `ws_version`.
2. Does `stanza release prerelease` work on the feature branch, in its worktree?
   **Answered 2026-10-14: yes, once the branch is on origin.** Tested with stanza
   1.5.0 on a throwaway feature branch in a `.worktrees/` worktree off `dev`
   (since deleted):
   - `--local -y` bumped `0.11.7a0 -> 0.11.7a1` on the current branch, committing
     `WebSearcher/__init__.py`, `pyproject.toml`, and `uv.lock` as
     `version [prerelease]: 0.11.7a1`.
   - Without `--local`, preflight fetches `origin/<branch>` and fails when the
     branch is not on origin (`couldn't find remote ref`), or is ahead of or
     behind it. After the bump it runs `git push origin <branch>` itself.
   - So push the branch and keep it level before each bump; a and c say so.
     The remote path was read from stanza's source, not run, to avoid pushing a
     throwaway branch.
   - stanza's version check accepts only `major.minor.patch` with an optional
     `aN`, so four-segment strings are refused as well as anything below
     `v0.11.6`.
