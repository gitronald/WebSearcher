---
status: done
branch: feature/v0.9.0-script-cleanup
created: 2026-06-05T16:02:29-07:00
completed: 2026-06-05T17:37:50-07:00
pr: https://github.com/gitronald/WebSearcher/pull/152
---

# Consolidate .claude/skills from 8 to 4 and absorb every skill-only script

## Problem

Plan 037 left an open follow-up (TODO line 3): the eight local skills in `.claude/skills/`
overlap, several are stale, and the scripts they call are split between `scripts/` (git-tracked)
and the skill dirs. A review fleet mapped the skills, their inputs, their relationships, and their
script dependencies, then verified the findings against the files. Two overlap clusters drive
everything:

1. **"Inspect / diagnose / fix one SERP"** — `serp-view`, `parser-update`, and `compare-selectors`
   all drive the same three inspection scripts (`show_parsed.py`, `show_serp.py`,
   `demo_screenshot.py`) against the same modified-parser-file artifact. `serp-view` *is*
   parser-update's inspection phases (1+3) extracted; `compare-selectors` *is* its Phase-7 step-5
   extracted. parser-update literally invokes `/compare-parsed` and `/compare-selectors`.
2. **"Did my parser change alter parsed output?"** — `parser-regression`, `reparse`, and
   `compare-parsed` are three flavors of the same before/after diff, differing only in the
   **baseline** they diff against. `reparse` is stale/broken (dead `serps-v*` glob → `IndexError`;
   old list-style `parse_serp` API).

The blocker to absorbing scripts into their owning skill (the way `reparse_demo.py` already was) is
**sharing**: `show_parsed.py` serves four skills, so it can't live in any one skill dir. Combining
the overlapping skills is the lever that unlocks absorption. `survey_ai_overviews.py` is the only
script no skill references — it stays in `scripts/` regardless.

## Final design: 8 → 4 skills, `scripts/` 9 → 1 file

| Skill | Status | Absorbs | Scripts bundled in the skill dir |
|---|---|---|---|
| **`serp-inspect`** (new) | merge target | serp-view + parser-update + compare-selectors | `show_parsed.py`, `show_serp.py`, `demo_screenshot.py` |
| **`compare-parsed`** (keep name) | merge target | parser-regression + reparse | `reparse_demo.py` (moves in from `parser-regression/`) |
| **`corpus-curate`** | keep as-is | — | `_common.py`, `profile_fixture_corpus.py`, `compare_drop_signatures.py`, `verify_corpus.py` |
| **`parse-bench`** | keep as-is | — | `bench_parse.py` |

End state: `scripts/` holds only `survey_ai_overviews.py`; every script that exists only to serve a
skill lives inside its owning skill dir. All four surviving skills keep `disable-model-invocation: true`.

### `serp-inspect` — the single "look at / diagnose / fix a parser on one stored SERP" workflow

Structured top-down so the lightweight path stays one command deep:

- **Tier 1 — read-only views** (= old `serp-view`): parsed-results table (`show_parsed.py`), served
  cleaned HTML on `:8765` (`show_serp.py`), component-overlay screenshot (`demo_screenshot.py`).
- **Tier 2 — diagnose + fix** (= old `parser-update`'s 7 phases): carries all accumulated
  parser-debugging lore verbatim (is_valid guard audits, hollow-details rules, structural-signal-
  over-header-text, validate-a-signal-against-the-whole-corpus).
- **Tier 3 — selector verification** (= old `compare-selectors`): git-diff the `css()`/`css_first()`/
  `_slx` selectors a parser edit changed; run on each modified file as the apply-step gate.

parser-update's old cross-skill calls (`/compare-parsed`, `/compare-selectors`) become internal
references: Tier 3 *is* the selector diff (no external slash-command), and the regression gate points
at the merged `compare-parsed` skill.

### `compare-parsed` — the single "did my parser change move parsed output?" check (3 modes by baseline)

| Mode | Compared against | Arg | Corpus | Mechanism | From |
|---|---|---|---|---|---|
| **Stash diff** (lead with this — fast inner loop) | your uncommitted changes (HEAD) | a data-dir path | one `data/demo-ws-v*/serps.json` | parse → `git stash` → parse → pop; diff per-query type/error counts | compare-parsed (already correct) |
| **Corpus sweep** | another branch/checkout | none (flags `--glob`/`--limit`/`--out`) | `data/demo-ws-*/serps.json` | run `reparse_demo.py` on two checkouts, diff key-sorted NDJSON | parser-regression |
| **Targeted vs saved** | the saved `parsed.json` snapshot | `serp_id` / prefix / query / `all` | `tests/fixtures/serps.json.bz2` | reparse, diff vs `parsed.json`, write `reparsed.json` | reparse (rebuilt correctly) |

`reparse` is retired into this skill, not preserved verbatim: it is rebuilt correctly — single
`Path('tests/fixtures/serps.json.bz2')` (no glob/`[-1]`), `ws.parse_serp(serp['html'])['results']`
(not the old whole-dict list API), before-side located by iterating `data/demo-ws-v*/parsed.json`.
`reparse_demo.py` moves from `.claude/skills/parser-regression/` into `.claude/skills/compare-parsed/`
(no path surgery — it already uses cwd-relative `Path('data')`). The stash mode's scratch files move
off `/tmp` → gitignored `data/parsed_before.json` / `data/parsed_after.json`, and the SKILL.md notes
the stash mode requires an editable install (else it silently compares identical installed code and
falsely reports "no regression").

### `corpus-curate` and `parse-bench` — clean 1:1 owners, absorb their scripts

- `corpus-curate` absorbs the corpus family: `profile_fixture_corpus.py`, `compare_drop_signatures.py`,
  `verify_corpus.py`, and their shared `_common.py` (the three do a bare `from _common import …`, so
  they travel together; the script's own dir stays on `sys.path[0]`). Flip `_common.CORPUS_FIXTURE`
  to cwd-relative `Path('tests/fixtures/serps.json.bz2')` (it is `__file__`-relative today and would
  silently resolve wrong from the gitignored dir). Prune `_common`'s dead ads-salvage helpers
  (`parse_results`, `type_subtype_counts`, `subtypes_for_type`, `components_missing_subtype`, the
  parquet `load_html_cache`/`save_html_cache`/`load_html_by_serp_ids`) — zero in-repo callers; keep
  only `load_serp_records`, `serp_label`, `CORPUS_FIXTURE`.
- `parse-bench` absorbs `bench_parse.py`. Replace `REPO_ROOT = Path(__file__).resolve().parent.parent`
  with `Path('.')`, and drop the `.relative_to(REPO_ROOT)` echoes and `cwd=REPO_ROOT` in `git_info`
  (paths are already repo-relative; `REPO_ROOT` is load-bearing at ~7 sites, not just output paths).
  The `serps*.json.bz2` fixtures glob still matches the single file — no edit. `bench_parse` keeps
  writing into the **tracked** `tests/benchmarks/` tree, so benchmark history stays in git.

## Tracking decision (resolve tracked `scripts/` → gitignored skill dir)

`.claude/skills/` is gitignored (`.gitignore:3`). Absorb a script into its owning skill dir
(accepting loss of git tracking/history) only when (a) exactly one surviving skill owns it after the
merges and (b) every tracked artifact that references it is repointed first. This is the deliberate
`reparse_demo.py` model — dev-only harnesses that run only inside an interactive agent session from
the repo root, never in CI or a clean `pip install`. Verified prerequisites: `.claude/skills/` is
gitignored; **no** `.github/` workflow invokes any of the 9 scripts (CI runs only ruff/pyrefly/
pytest), so no absorption breaks a live gate; `survey_ai_overviews.py` is referenced by zero skills,
so it stays tracked in `scripts/` unconditionally.

## Staleness fixes to fold in during the rewrites (14, all file-verified)

- **serp-inspect / Tier 2 (parser-update):** drop the bogus `parse_serp(soup, extract_features=True)`
  kwarg (`:79`, raises `TypeError`) → `parsed = ws.parse_serp(soup)` then `pl.DataFrame(parsed['results'])`;
  replace bs4 `elem.find_all(attrs={'role':'heading'})` (`:100`, no such method on a `LexborNode`)
  → `elem.css('[role="heading"]')`; fix dead `serps-v*` / `serps-*.json.bz2` globs (`:156`, `:222`)
  → `serps.json.bz2`; reword the `demo_screenshot` "BeautifulSoup elements" note (`:224`) →
  "selectolax nodes"; correct the overstated `show_parsed` column claim (`:73`).
- **serp-inspect / Tier 1 (serp-view):** correct the `show_parsed` column claim (`:17`) → the real
  columns are `type`/`title`/`url` (+ optional details via `--details`); fix the dangling Notes
  pointer (`:35`) to name only `compare-parsed` (reparse/compare-parsed-as-separate-skills are gone).
- **serp-inspect / Tier 3 (compare-selectors):** rewrite the bs4-era "What to Compare" inventory
  (`:34-41`) for selectolax — drop `find()`/`find_all()`, `get_text_by_selectors()`, `find_all_divs()`,
  `Selector(...)`/`header_selectors`, and the `WebSearcher.utils` `get_link`/`get_text` mentions
  (all gone after the selectolax rewrite); compare `.css(...)`/`.css_first(...)` args and the `_slx`
  helpers parsers actually call; keep the still-valid `_ARIA_RATING_RE` module-regex bullet.
- **compare-parsed (reparse fold):** rebuild correctly per the Targeted-vs-saved mode above.
- **compare-parsed (stash mode):** move scratch off `/tmp` → gitignored `data/parsed_before.json` /
  `data/parsed_after.json`. (Its `parse_serp` usage `parsed.get('results')` is already correct — do
  NOT "fix" it.)
- **compare-parsed Notes:** rewrite the old `parser-regression`/`reparse`/`compare-parsed` cross-skill
  pointers (they are all now this one skill or modes of it).
- **`.claude/skills/README.md`:** replace the serp-view / parser-update / compare-selectors / reparse /
  parser-regression rows with `serp-inspect` + `compare-parsed`; fix the companion-scripts table (no
  listed script lives in `scripts/` anymore); correct the `show_parsed` column description.
- **`corpus-curate/SKILL.md:24`:** drop the false "also a CI guard; exits non-zero on failure"
  self-description (nothing in CI invokes it) — or reword per Open Decision 1.
- **`docs/guides/fixture-corpus.md`:** repoint the live command blocks to the bundled
  `.claude/skills/corpus-curate/` paths; rename `verify_drops.py` → `verify_corpus.py` and rewrite the
  stale plan-032-specific prose to the generalized guard; mark the retired `build_fixture_corpus.py`
  mention as historical.
- **`docs/guides/selectolax-parsers.md:200`:** repoint the live perf-gate command from
  `scripts/bench_parse.py` to `.claude/skills/parse-bench/bench_parse.py`.
- **`pyproject.toml`:** repoint the cosmetic `bench_parse` comment.
- **`README.md` (~`:76-80`):** repoint the user-facing `scripts/show_parsed.py` walkthrough off the
  dev-only script (see Open Decision 2).

## Open decisions

1. **Corpus integrity as a real CI gate.** `verify_corpus.py`'s checks (unique serp_ids, every record
   noted, every record yields `main_layout` + ≥1 result) run nowhere in CI today. Options: (a) promote
   the three assertions to a tracked `tests/test_corpus_integrity.py` so they run under the existing
   pytest job *and* absorb the script for the rich `--dump` report; (b) accept skill-only and drop the
   false "CI guard" line from the SKILL.md.
2. **README walkthrough replacement.** `README.md` points end users at the dev-only
   `scripts/show_parsed.py` (typer+polars, never shipped — plan-037 flagged this as a bug). It takes a
   query and has `--cat-width`/`--details`/`--list`; the obvious `ws-demo parse` takes a *file* and
   lacks those flags. Verify `ws-demo`'s actual output shape first, then repoint to it if a per-query
   table fits, else fall back to the `ws.parse_serp(...)['results']` snippet already in the README's
   Step-by-Step section.
3. **Git history of absorbed scripts.** Moving `_common.py` (~155 lines) and `bench_parse.py` (~296
   lines) from tracked `scripts/` into the gitignored skills tree deletes them from version control
   (irreversible). `reparse_demo.py` set the precedent but was a fresh single-commit file with no
   history to lose. Options: (a) proceed, accept history loss; (b) snapshot/archive before `git rm`;
   (c) keep these two tracked in `scripts/` (scripts/ ends with 3 files instead of 1).

## Implementation order

1. **Doc repoints first** (so no tracked artifact points at a script about to move): README walkthrough
   (per Decision 2), `docs/guides/fixture-corpus.md`, `docs/guides/selectolax-parsers.md:200`,
   `pyproject.toml` comment.
2. **Build `serp-inspect`:** create the dir, copy the three inspection scripts in, `git rm` them from
   `scripts/`, write the tiered SKILL.md (Tier 1/2/3) with staleness fixes applied and cross-skill
   calls internalized. Delete `serp-view/`, `parser-update/`, `compare-selectors/`.
3. **Fold into `compare-parsed`:** move `reparse_demo.py` in from `parser-regression/`; add the
   corpus-sweep + targeted-vs-saved modes; rebuild reparse correctly; move stash scratch off `/tmp`;
   note the editable-install caveat. Delete `parser-regression/` and `reparse/`.
4. **Absorb the corpus family** into `corpus-curate`: move the four files in, `git rm` from `scripts/`,
   flip `_common.CORPUS_FIXTURE` to cwd-relative. Prune `_common`'s dead helpers as a **separate,
   smoke-tested commit** (not folded into the move). Repoint the SKILL.md commands; edit `:24` per
   Decision 1.
5. **Absorb `bench_parse.py`** into `parse-bench`: move it in, `git rm` from `scripts/`, do the
   `REPO_ROOT` → `Path('.')` surgery, repoint the SKILL.md.
6. **Rewrite `.claude/skills/README.md`** for the new 4-skill set.
7. **Smoke-test from repo root** (mandatory — the path flips fail *silently* from the new location):
   a `show_parsed` render, a corpus `profile`/`verify` run, and a `bench_parse --no-save` run. Confirm
   `scripts/` now contains only `survey_ai_overviews.py`.
8. **Commit in logical chunks** (doc repoints → each skill merge → path surgery → `_common` prune).
   Append a Log entry to plan 037 referencing this plan, mark TODO line 3 done. Do NOT push/merge
   unless asked.

## Out of scope / loose ends

- No public-API, `BaseResult`, or `SERPFeatures` schema changes; the pytest snapshot suite must stay
  green throughout (`uv run pytest`).
- `survey_ai_overviews.py` stays in `scripts/` (no skill references it).
- The irreversible `git rm` of scripts with real history (Decision 3) is gated on an explicit go-ahead.

## Log

### 2026-06-05 — open decisions resolved; activated

1. **Corpus CI gate → option (a):** promote `verify_corpus.py`'s three assertions to a tracked
   `tests/test_corpus_integrity.py` under the existing pytest job, AND still absorb the script into
   `corpus-curate` for its `--dump` report.
2. **README walkthrough → "add a `ws-demo` flag first":** give a `ws-demo` subcommand the
   `show_parsed`-equivalent ergonomics (column width / details against stored demo data) so the README
   example keeps its query-keyed shape, then repoint off the dev-only `scripts/show_parsed.py`.
3. **Git tracking → "proceed, accept it":** `git rm` `_common.py` + `bench_parse.py` into their
   gitignored skills (past commits stay recoverable; future edits live in the local skills tree).
   `scripts/` ends at one file (`survey_ai_overviews.py`).

### 2026-06-05 — implemented (8 -> 4 skills, scripts/ 9 -> 1)

Done on `feature/v0.9.0-script-cleanup` in five tracked commits (`33072ae`, `c97103d`, `00202b2`,
`e32e1f5`, + this wrap-up). The skill-dir changes themselves are gitignored; the tracked footprint is
the `ws-demo show` subcommand, the script removals, the new pytest test, and the doc repoints.

**Final skill set:**
- `serp-inspect` (new) = serp-view (Tier 1 views) + parser-update (Tier 2, 7-phase fix lore preserved
  verbatim) + compare-selectors (Tier 3 selector diff). Bundles `show_serp.py` + `demo_screenshot.py`.
- `compare-parsed` = its own stash diff (Mode 1) + parser-regression (Mode 2 corpus sweep) + reparse
  (Mode 3 targeted-vs-saved, rebuilt correctly). Bundles `reparse_demo.py` (moved from
  `parser-regression/`).
- `corpus-curate` (kept) bundles `_common.py` + the three corpus scripts.
- `parse-bench` (kept) bundles `bench_parse.py`.

**Decisions as implemented:**
1. Corpus gate → added tracked `tests/test_corpus_integrity.py` (unique ids / note / main_layout / >=1
   result, parametrized per record) AND absorbed `verify_corpus.py` for its `--dump`. Dropped the
   false "also a CI guard" line from the SKILL.md and `docs/guides/fixture-corpus.md`.
2. README → built a new package-native `ws-demo show "<query>"` subcommand (`WebSearcher/demos/show.py`,
   runtime-deps-only stdlib table, `--list`/`--details`/`--max-width`) and repointed the README
   walkthrough to it. **Refinement:** since `ws-demo show` fully covers `show_parsed.py`, that script
   was *retired* rather than bundled into `serp-inspect` (DRY — one implementation), and every consumer
   (README, serp-inspect Tier 1/3, compare-parsed spot-check) now points at `ws-demo show`.
3. Git tracking → proceeded; `scripts/` now holds only `survey_ai_overviews.py`.

**Path surgery (verified by smoke tests from the new gitignored locations):** `_common.CORPUS_FIXTURE`
and `bench_parse`'s `REPO_ROOT` chain flipped to cwd-relative (dropped `REPO_ROOT`, `.relative_to()`,
and `cwd=REPO_ROOT`); `_common` pruned to `load_serp_records`/`serp_label`/`CORPUS_FIXTURE` (7 dead
ads-salvage helpers removed, zero callers verified). All staleness fixes folded in (parse_serp kwarg,
`elem.css('[role="heading"]')`, `serps.json.bz2` globs, selectolax wording, show_parsed column claims,
the pyproject bs4/lxml comment that named retired scripts). `.claude/skills/README.md` rewritten for
the 4-skill set.

**Verification:** `uv run pytest` → 408 passed, 4 skipped, 80 snapshots. Each merged skill's primary
command smoke-tested from repo root (`ws-demo show`, the three corpus scripts, `bench_parse --no-save`,
`reparse_demo`). ruff clean across `.claude/skills/` and the package. Not pushed/merged.

### 2026-06-05 — revision: keep `bench_parse.py` tracked in `scripts/`

Reverted the `bench_parse.py` absorption (Decision 3 applied to it) at the user's request: unlike the
other absorbed scripts, the bench is the **perf gate** — it writes to the *tracked*
`tests/benchmarks/results.jsonl` and is cited by the tracked `docs/guides/selectolax-parsers.md`, so
burying it in the gitignored skill tree was the wrong home. Restored the original
`scripts/bench_parse.py` (with its `__file__`-relative `REPO_ROOT`, correct for `scripts/`), deleted
the skill copy, and repointed `parse-bench/SKILL.md`, the guide, the pyproject comment, and the skills
README back to `scripts/bench_parse.py` — the `parse-bench` skill now *wraps* the tracked script
instead of bundling it. Net: `scripts/` holds two tracked dev tools (`bench_parse.py`,
`survey_ai_overviews.py`); the other skill-only scripts stay absorbed. `_common.py` was left absorbed
in `corpus-curate` (only `bench_parse` was flagged). Smoke-tested `scripts/bench_parse.py --no-save`
from repo root; ruff clean.

### 2026-06-05 — revision: bench into the package, survey into a new skill, scripts/ removed

Per follow-up direction, gave the last two `scripts/` files a permanent home and emptied `scripts/`:

- **`bench_parse.py` -> `WebSearcher/bench.py`** (the "fold it in" option). Rewritten off `typer` to
  `argparse`/stdlib so the package gains no dev dependency (verified `import WebSearcher.bench` pulls no
  typer), mirroring the demos. Run via `python -m WebSearcher.bench` (no console entry point — unlike
  `ws-demo` it needs the `tests/` tree and can't run from a bare wheel). `REPO_ROOT =
  __file__.parent.parent` resolves to the repo root from `WebSearcher/bench.py` just as it did from
  `scripts/`, so the `tests/benchmarks/results.jsonl` / `tests/fixtures` paths are unchanged. Added
  `WebSearcher/bench.py` to the coverage `omit` (a dev tool, like `search_methods/`). Repointed
  `parse-bench/SKILL.md`, the selectolax guide, the pyproject snakeviz comment, and the skills README.
- **`survey_ai_overviews.py` -> new `explore-ai-overview` skill.** It already used argparse + cwd-relative
  globbing, so it moved unchanged into `.claude/skills/explore-ai-overview/` with a new SKILL.md (survey
  AI-overview HTML structure across demo datasets; also an AI-overview regression check). `git rm` from
  `scripts/`.
- **`scripts/` removed** — both remaining files moved out, stale `__pycache__` cleared, the empty dir
  deleted. The repo no longer has a `scripts/` directory.

Skills are now **5** (`serp-inspect`, `compare-parsed`, `corpus-curate`, `parse-bench`,
`explore-ai-overview`). Verified: `uv run pytest` 408 passed / 80 snapshots, `python -m WebSearcher.bench
--no-save` and the survey script both run from the repo root, ruff clean.

## Retrospective

Shipped via PR #152 (merged into `feature/v0.9.0`). The 8 → 4 consolidation (later 5, once
`explore-ai-overview` absorbed the lone surveying script) was driven by a review fleet and held up:
combining the overlapping inspection skills was the lever that freed the shared inspection scripts to be
absorbed, and `ws-demo show` replaced `show_parsed.py` outright. Merging back into `feature/v0.9.0`
required a 35-commit catch-up and renumbering this plan 035 → 038 (and the audit 033 → 037) to clear
collisions with plans the version branch had created in parallel — a reminder to cut cycle topic branches
off the *current* version-branch tip and to keep them short-lived. Final suite on the merged code: 425
passed, 87 snapshots, CI green on 3.12/3.13/3.14.
