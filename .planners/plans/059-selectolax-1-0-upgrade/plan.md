---
id: 59
slug: selectolax-1-0-upgrade
status: done
branch: feature/selectolax-1-0-upgrade
created: 2026-10-14T20:12:13-07:00
concluded: 2026-10-14T21:50:21-07:00
pr: https://github.com/gitronald/WebSearcher/pull/200
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
| [a](subplans/a-pre-1-0-baseline-bench.md) | Bump to selectolax 0.4.13 and benchmark the baseline | done |  |
| [b](subplans/b-study-1-0-release-notes.md) | Study the selectolax 1.0 release notes for our use | done |  |
| [c](subplans/c-upgrade-to-1-0.md) | Upgrade selectolax to 1.0 and bump the prerelease | done |  |
| [d](subplans/d-post-upgrade-bench.md) | Benchmark and verify selectolax 1.0 against the baseline | done |  |
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
- **2026-10-14T20:45:08-07:00** — PR opened: https://github.com/gitronald/WebSearcher/pull/200
- **2026-10-14T21:20:07-07:00** — 059a and 059b done; see their Logs.
  - Bench harness fix landed in 059a (`gc.collect()` after each timed SERP); rows before this effort are not comparable with its rows.
  - Follow-up plan candidates from 059b: (1) move `get_text`'s strip+separator path to native `text(skip_empty=True)` plus a filter for non-ASCII-whitespace fragments, with its own byte-identity proof; (2) `LexborHTMLParser(..., encoding=True)` for `bytes` input to `make_soup`.
- **2026-10-14T21:50:53-07:00** — 059c and 059d done. Measured effect per step (same-session within each step, not across):
  - 0.4.10 -> 0.4.13 (059a): 1556.9 -> 1571.2 ms corpus total, +0.9%, at the noise floor; no measurable change.
  - 0.4.13 -> 1.0.0 (059d, A B B A): 1569.2 -> 828.0 ms, -47.2%, from lexbor parsing (`make_soup` 2.2x) and CSS matching; `text()`-only frames barely moved.
  - Output: snapshot suite byte-identical at every step; pyrefly needed test-only narrowing for 1.0's corrected `css_first` stubs (059c).
- **2026-10-14T21:51:27-07:00** — Implemented: 25 commits ahead of `dev`.
- **2026-10-14T21:56:48-07:00** — Both follow-up candidates from 059b retired, after measuring them on selectolax 1.0.0 (`0.11.7a2`); no follow-up plan.
  - (1) Native `skip_empty` path for `get_text`'s strip+separator case: not worth it. On 1.0.0 that case is 2,747 calls per corpus pass costing about 9 ms of about 830 ms (0.9%), so even a free native version would save about the benchmark's noise floor, while needing a filter for the non-ASCII-whitespace fragments `skip_empty` keeps (059b: 1.8% of nodes differ) and its own corpus-wide identity proof. Per pass, the native `get_text` fast path is 10,953 calls and 22 ms, the script/style walker case 128 calls and 8 ms. Repeat: `uv run python .planners/plans/059-selectolax-1-0-upgrade/textpath_059f.py`.
  - The release note's "text up to 5x faster" was checked directly (best of 5, two passes per version, `uv run --no-project --with selectolax==<v> --with orjson python .planners/plans/059-selectolax-1-0-upgrade/text_speed_059f.py`): per-node calls got faster (`text(deep=True)` on 202,794 divs 439-454 -> 181-185 ms, 2.4x; `text(deep=False)` on 71,495 text nodes 59-60 -> 40-41 ms, 1.5x), whole-document `text()` did not (71-98 vs 86-95 ms; with `separator=" ", strip=True` 73-75 vs 72-73 ms). Parsing for comparison: 459-466 -> 206-209 ms, 2.2x. The parser already sends most `get_text` calls through native `text()`, so it already gets the per-node gain.
  - The remaining Python walker time is in early-exit consumers that a full native `text()` cannot replace: `ExtractorMain.is_valid` 26 ms/pass (2.8%, stops after 15 characters) and `has_text` 12 ms/pass (1.3%, stops at the first non-blank fragment). Repeat: `uv run python .planners/plans/059-selectolax-1-0-upgrade/walker_budget_059f.py`.
  - (2) `LexborHTMLParser(..., encoding=True)` for `bytes` input to `make_soup`: retired. It is a behavior change, not a speedup: `make_soup` decodes `bytes` as UTF-8 with replacement, and detection would change output for non-UTF-8 input. The one in-repo `bytes` path is `utils.load_soup(fp, zipped=True)`, which hands brotli-decompressed bytes to `make_soup` (`demos/parse.py` calls `load_soup`); the parser's own callers pass `str`. Revisit only if a non-UTF-8 SERP shows up. (Corrected at close: this entry first said no in-repo caller passes `bytes`.)
- **2026-10-14T22:04:58-07:00** — Close-out. Review gate run at medium level (code review with finders and verification) on PR #200; check gate clean (ruff check, ruff format --check, pyrefly 0 errors, 644 tests and 102 snapshots passing, coverage 79.3%).
  - Review follow-up: one confirmed finding, fixed in `b2a11c6`: the umbrella Log and subplan b said no in-repo caller passes `bytes` to `make_soup`, but `utils.load_soup(fp, zipped=True)` does (brotli-decompressed bytes; `demos/parse.py` calls `load_soup`). The retirement of the `encoding=True` follow-up stands on its primary reason (detection changes output for non-UTF-8 input); the text now names the bytes path. No regression test: a plan-text correction, no code changed.
  - Conscious no-ops: the CHANGELOG's "about 10-15%" effect of the bench gc fix rests on console timings in 059a's Log, not committed rows (the pre-fix runs were killed before writing any), and the entry already says which rows are comparable; the per-file test narrowing helpers (`comp`, `_node`, `_wrap`) duplicate one another, but they predate this effort, which only typed them, so consolidation is a separate refactor; `version("selectolax")` is looked up twice per bench run, which is negligible and keeps the lookup visible at each site.
- **2026-10-15T08:03:01-07:00** — Added sidecar `bench-history.md`: every recorded parse-timing run from the bs4 era to selectolax 1.0, with a source column (plan Log vs `tests/benchmarks/results.jsonl`) and corpus size, Python, and iterations per row.
    - The clean bs4 -> selectolax comparison is plan 026's final A/B (`9e633bf` vs `94bc682`): about 98 -> 19.0 ms/SERP, ~5.2x; the 0.9.0 CHANGELOG's "~2x" came from an earlier adapter-era A/B with an outlier bs4 side.
    - Plan 026's "122.4 ms bs4 baseline" (`68b8423`) is the selectolax adapter build, not bs4, so the `convert-bs4-to-selectolax` skill's "~3.4x (122 -> 36 ms)" is adapter -> native.
    - Unresolved: a ~2.5x drop between plan 035 (Python 3.13.12) and plan 036 (3.14.3) on the same 87-SERP corpus, with no same-session check isolating the cause.

## Handoff

State: closed. All four subplans done; PR #200 reviewed (medium gate, one plan-text
correction) and merged to `dev` at `0.11.7a2` with selectolax 1.0.0. The baseline
worktree from d and the feature worktree are removed. Nothing remains, and no
follow-up plan is owed: both candidates from b were retired after measurement (see
the umbrella Log).

Not verified: the speedup on hardware other than this machine, and on interpreters
other than CPython 3.14.8. Earlier `results.jsonl` rows (June, Python 3.14.3, 80-87
SERPs) are not comparable with this effort's rows. The stable `0.11.7` release that
carries this to users is out of scope here and follows the normal release path.

Questions:

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

## Retrospective

- **The two-step split paid for itself in attribution, not in findings.** 0.4.10 -> 0.4.13 was flat (+0.9%, at the noise floor) and 0.4.13 -> 1.0.0 was -47.2% on the corpus, so the whole win is the 1.0 release. Without the split the same number would have been reported with a weaker claim about where it came from.
- **The release notes were wrong about where our time would go.** b capped the advertised 5x `text()` speedup at about 10% of profiled time and that cap held; the real gain came from lexbor parsing (2.2x on `make_soup`) and CSS matching, which b had only marked `watch`. Reading notes tells you what to check, not what will move; the back-to-back profile with identical call counts is what told the story.
- **A benchmark harness bug surfaced before any upgrade work and changed the baseline.** The pre-fix bench leaked parse trees with gc disabled and could not finish a full corpus run; fixing it moved timings 10-15%, so every earlier row in `results.jsonl` became non-comparable. Check the measuring instrument first when a plan's deliverable is a measurement.
- **Byte-identity gating was cheap and decisive.** The snapshot suite passed unchanged at each step, so none of the 38 1.0.0 release items needed a per-component diagnosis; the only code change the upgrade forced was type narrowing in tests, because 1.0's stubs stopped lying about `css_first`.
- **Testing a tempting "adopt now" item killed it.** Native `skip_empty` looked like a free swap for `get_text`'s slow path and differed on 1.8% of nodes (non-ASCII whitespace), then measured at under 1% of parse time once 1.0 was in. Measure before scheduling a follow-up; both candidates retired without a plan.
- **Review caught a plan claim the code contradicted.** "No in-repo caller passes `bytes`" was false (`load_soup(zipped=True)`); the conclusion survived on its other reason, but a grep at writing time would have avoided the correction. Verify "no caller" claims the same way as code-usage claims.
