---
status: done
branch: feature/v0.9.0-script-cleanup
created: 2026-06-05T09:53:50-07:00
completed: 2026-06-05T17:37:50-07:00
pr: https://github.com/gitronald/WebSearcher/pull/152
---

# Audit scripts/: absorb demos into the package, extract skills, retire one-offs

## Problem

`scripts/` has accumulated 20 scripts (plus an untracked `ads-no-subtype/` folder) across
seven years and ~30 plans. They are a mix of three different things wearing the same coat:
end-user **demos**, maintainer **dev tools**, and finished **one-off investigations**. Three
concrete pains motivate a cleanup:

1. **Demos don't run after a clean install.** README tells users to run `uv run demo-search`
   (`README.md:73`), but the `demo-search`/`demo-searches` entry points — and almost every
   `demo_*` script — import `typer` and `polars`, which are **dev-group dependencies, not
   runtime** (`pyproject.toml:10-19` lists `requests, selectolax, tldextract, brotli, pydantic,
   undetected-chromedriver, selenium, protobuf, orjson` — no typer, no polars). A user who runs
   `pip install WebSearcher` then `demo-search` gets a `ModuleNotFoundError`. The demos need to
   be runnable from the package, not from the dev checkout.
2. **Repeatable maintainer workflows live as bare scripts.** Several scripts encode a *procedure
   with judgment* (fixture-corpus curation, SERP inspection, parser-regression diffing) that an
   agent should drive. Those are a better fit for `.claude/skills/` than for `scripts/`.
3. **Finished one-offs and a 31 GiB data folder are still on disk.** Half the scripts were built
   for a specific, now-closed plan and will never run again (their inputs were deleted, or they
   write to `/tmp`, or they hardcode `/mnt/c/Users/rer/...` private paths). `scripts/ads-no-subtype/`
   alone holds a **31 GiB** regenerable parquet (`du -sh` = 31G).

This plan maps every script to its purpose and driver, then assigns each a disposition:
**absorb** into the `WebSearcher` package, **extract** to a `.claude/skill`, **keep** in `scripts/`,
or **retire**.

## Inventory and disposition

Driver = the creating commit and the plan that prompted it. Deps = third-party imports outside the
runtime set (the reason a script won't run on a clean install).

| Script | Purpose | Driver | Non-runtime deps | Disposition |
|---|---|---|---|---|
| `demo_parse.py` | Offline: parse one local `.html` and print a results table | `f8f831a` 2019 initial; polars added `487209f` | polars | **Absorb** (zero-dep offline demo) |
| `demo_search.py` | Canonical: search one query, parse, save serps/parsed/searches | `f8f831a` 2019; plan 014 | typer, polars | **Absorb** (flagship demo) |
| `demo_search_headers.py` | Single query via `requests` with custom headers | `d6d46f0` 2023; fix `25c4fdb` | typer, polars | **Absorb** (feature demo) |
| `demo_locations.py` | Localization walkthrough (download geotargets, Boston/pizza) | `c9dd5cc` 2019; plan 031 | polars | **Absorb** (localization demo) |
| `demo_searches.py` | Bulk query battery to generate a component-diverse corpus | `2da519c` 2023; plan 014 | typer, polars | **Keep** (dev corpus generator) |
| `demo_screenshot.py` | Render saved SERP HTML headless, overlay classified components | `6bec20a` 2026; plans 005/026 | typer | **Skill** (`/serp-view`) or keep |
| `reparse_demo.py` | Reparse the demo corpus to NDJSON for cross-checkout regression diffs | `0e76869` 2026 (single commit) | typer | **Skill** (`/parser-regression`) |
| `show_parsed.py` | Print a compact parsed-results table for a stored query | `a5f06d0` 2026; plan 021; README | typer, polars | **Skill** (`/serp-view`) or keep |
| `show_serp.py` | Serve a saved SERP's HTML on localhost for visual inspection | `51cb976` 2026; plan 021 | typer, bs4 | **Skill** (`/serp-view`) or keep |
| `parsed_to_csv.py` | Flatten `parsed.json` -> results CSV | `a6b2579` 2026 ("temp utility script") | polars | **Retire** (self-described temp) |
| `bench_parse.py` | Benchmark/profile `parse_serp` over the fixture corpus | `ca43a31`-era; plans 017/023/026 | typer | **Keep** or **Skill** (`/parse-bench`) |
| `profile_fixture_corpus.py` | Profile each corpus record's unique contribution (prune aid) | `ca43a31` 2026; plan 032 | (none; orjson) | **Keep**/**Skill** (`/corpus-curate`) |
| `compare_drop_signatures.py` | Cluster corpus records by component signature (prune aid) | `ca43a31` 2026; plan 032 | (none; orjson) | **Keep**/**Skill** (`/corpus-curate`) |
| `verify_drops.py` | Integrity guard: dropped IDs absent, ids unique, notes present, layouts/pairs covered | `f5b6eb4` 2026; plan 032 | (none; orjson) | **Keep** (generalize, drop plan-032 constants) |
| `build_fixture_corpus.py` | One-shot: merged 7 old fixtures into `serps.json.bz2` | `30dcaef` 2026; plan 032 | (none; orjson) | **Retire** (inputs deleted, non-rerunnable) |
| `condense_fixtures.py` | Mint deprecated per-version `serps-v*.json.bz2` from demo data | `409786e` 2026; plan 008 | typer | **Retire** (emits abandoned layout) |
| `diff_parsers.py` | bs4+lxml vs selectolax parity harness over fixtures | `d4ead9e` 2026; plan 026 | typer, bs4 | **Retire** (026 shipped) or keep as parity check |
| `dump_ai_overview_html.py` | Dump AI-overview HTML from demo SERPs to `/tmp` for parser design | `53341d` 2026; plans 021/024 | bs4 | **Retire** (investigation done) |
| `inspect_ai_overview_structure.py` | Print AI-overview heading skeleton to find a section delimiter | `53341d` 2026; plan 021 | bs4 | **Retire** (investigation done) |
| `survey_ai_overviews.py` | Cross-SERP AI-overview structural summary; reused as regression check | `53341d` 2026; plans 021/022 | bs4 | **Keep** (maintained, reused) |
| `ads-no-subtype/` (folder) | Private Jan-2026 ad-classification bug probe + **31 GiB** HTML cache | gitignored, no history, no plan | polars, **pandas (undeclared)** | **Retire + reclaim disk** (confirm first) |

## Disposition details

### A. Absorb the demos so they run after `pip install` (the core goal)

`demo_parse`, `demo_search`, `demo_search_headers`, and `demo_locations` are the four genuine
end-user demos. They fail on a clean install only because of `typer` (CLI sugar) and `polars`
(used solely to pretty-print a results table). Neither is essential to the demo.

Recommended approach (hybrid — see Open Decisions for the alternatives):

1. **Move demo logic into a `WebSearcher.demo` subpackage** (`WebSearcher/demo/__init__.py`,
   `parse.py`, `search.py`, `headers.py`, `locations.py`) that imports **only runtime deps**:
   - Replace `polars` table printing with a small plain-text table helper (or render the existing
     `ParsedSERP`/results dicts directly). The demos already operate on `parse_serp`'s dict output.
   - Replace `typer` with `argparse`, or expose a single `python -m WebSearcher.demo <cmd>` CLI.
2. **Keep `demo_parse` zero-extra** — the simplest offline example (`parse one HTML, print`) must
   run with nothing beyond the runtime deps.
3. **Repoint the console entry points** in `[project.scripts]` at the new package module so
   `demo-search` / `demo-searches` resolve from the installed package, and update the README
   examples (`README.md:73`, `:79`) accordingly.
4. The thin `scripts/demo_*.py` wrappers can then be deleted or reduced to one-line shims that call
   the package (decide at implementation).

Net effect: `pip install WebSearcher && demo-search "election news"` works with no dev install.

### B. Extract repeatable workflows to `.claude/skills/`

These encode a maintainer procedure an agent should drive; a skill bundles the commands plus the
*methodology* (how to interpret the output, what to do next). Candidate skills:

- **`/serp-view`** — inspect a stored SERP: serve its HTML (`show_serp`), print the parsed table
  (`show_parsed`), and optionally screenshot with component overlays (`demo_screenshot`). The
  "reach for this first when debugging a SERP" primitive (plan 021's retrospective says as much).
- **`/corpus-curate`** — the plan-032 fixture-review methodology: `profile_fixture_corpus` (what
  each record uniquely contributes) + `compare_drop_signatures` (near-duplicate clusters) +
  `verify_drops` (integrity guard), with guidance on read-and-decide-then-prune.
- **`/parser-regression`** — `reparse_demo` on two checkouts, diff the NDJSON, surface changed
  records. The standard "did my parser change alter output?" check.
- **`/parse-bench`** — `bench_parse` (+ profiler) with the noise-floor gating rules already baked
  into its docstring (now writing `tests/benchmarks/results.jsonl`).

Skills wrap the scripts; the scripts themselves can stay in `scripts/` (the skill calls them) or
the logic can move into the skill — decide per skill at implementation. Start with the two
highest-value: `/serp-view` and `/corpus-curate`.

### C. Keep in `scripts/` (maintainer dev tools, not user-facing, not skill-shaped)

- `demo_searches.py` — bulk corpus generator (CAPTCHA handling, jittered delays); maintainer-run.
- `survey_ai_overviews.py` — maintained (plan 022) and reused as an AI-overview regression check.
- `verify_drops.py` — keep as an ongoing corpus-integrity guard, but **generalize**: the
  `PLAN032_DROPS` / `REQUIRED_LAYOUTS` constants are one-time; the generic checks (unique ids,
  every record noted, layouts/pairs covered) are what a recurring CI guard wants.
- `bench_parse.py`, `profile_fixture_corpus.py`, `compare_drop_signatures.py` — keep even if also
  surfaced via skills (the skills can shell out to them). Drop the dead old-layout glob fallback in
  `profile_fixture_corpus.py` (only `serps.json.bz2` exists now).

### D. Retire (finished one-offs)

- `parsed_to_csv.py` — commit message literally says "temp utility script."
- `build_fixture_corpus.py` — its 7 input fixtures were deleted by the same consolidation it ran;
  **non-rerunnable**. Keep only if build provenance is worth archiving (the plan-032 log already
  records it).
- `condense_fixtures.py` — emits the per-version layout plan 032 retired; plan 008 is done.
- `dump_ai_overview_html.py`, `inspect_ai_overview_structure.py` — plan 021/024 AI-overview
  delimiter hunt is done; writes to `/tmp`; untouched since creation.
- `diff_parsers.py` — plan 026 shipped selectolax; the parity harness has served its purpose
  (retire, or downgrade to an opt-in backend-parity check if worth keeping).

Before deleting, confirm nothing in `docs/` or README still instructs running them (README line 270
references `condense_fixtures.py` in a fixtures section — update or remove that example).

### E. `scripts/ads-no-subtype/` — retire and reclaim ~31 GiB (confirm before deleting)

A private, untracked (gitignored: `.gitignore:10`) Jan-2026 investigation into `type=='ad'` rows
with null `sub_type`. Both `.py` files hardcode machine-specific `/mnt/c/Users/rer/...` paths to
private audit data; `reparse_ads_no_subtype.py` imports **pandas, which is declared nowhere** in
`pyproject.toml`/`uv.lock`. The folder holds a **31 GiB** regenerable HTML-cache parquet
(`serps-ads-no-subtype.parquet`) — by far the largest disk item in the working tree.

This is not project code and will never run on another machine. **Recommend deleting the folder to
reclaim ~31 GiB.** Per the repo safety rule, a recursive/large delete must be confirmed with the
user first — this plan only proposes it; execution gets an explicit go-ahead.

## Open decisions

1. **Demo delivery mechanism** — (a) absorb into a runtime-dep-only `WebSearcher.demo` package
   [recommended]; (b) keep scripts as-is but add a `[project.optional-dependencies] demo = [...]`
   extra and tell users `pip install "WebSearcher[demo]"`; (c) hybrid: absorb the zero-dep
   `demo_parse`, add the `demo` extra for the browser demos. Affects how much is rewritten.
2. **Which skills to actually build** — all four candidates, or start with `/serp-view` +
   `/corpus-curate`?
3. **Delete the 31 GiB `ads-no-subtype/` folder now?** (reclaims the most disk; needs confirmation).
4. **`diff_parsers.py`** — retire outright, or keep as an opt-in backend-parity regression check?

## Implementation order

1. **Reclaim disk** (decision 3): delete `ads-no-subtype/` after confirmation. Cheap, high-value.
2. **Retire bucket D** one-offs: delete, update README line 270 and any doc references.
3. **Absorb demos** (decision 1): create `WebSearcher.demo`, drop polars/typer from the demo path,
   repoint `[project.scripts]`, update README demo examples, verify `demo-search` runs from a clean
   `uv run --no-project --with .` install.
4. **Generalize `verify_drops.py`**; drop the dead glob fallback in `profile_fixture_corpus.py`.
5. **Extract skills** (decision 2): `/serp-view` and `/corpus-curate` first.
6. Update `CHANGELOG`/README "Recent Changes" for the demo-install fix and the script reorg.

## Out of scope / loose ends

- Plan 031 references `scripts/update_locations.py`, which does not exist on disk — verify whether
  the geotargets-download logic was already absorbed into the package (relevant to the
  `demo_locations` absorb in step 3) before duplicating it.
- No public-API or `BaseResult`/`SERPFeatures` schema changes; the snapshot suite must stay green
  throughout (`uv run pytest`).

## Log

### 2026-06-05 — bucket E done (ads-no-subtype retired) + salvage

Activated. **Decision 3 resolved: retire the folder** — the user deleted
`scripts/ads-no-subtype/`, reclaiming ~31 GiB. Before it went, its reusable kernel was salvaged
into `scripts/_common.py` (commit `2da8dbc`): `parse_results` (rewritten for the current
`{"results", ...}` envelope — the original treated `parse_serp` as a bare list and was already
broken), the `(type, sub_type)` coverage summaries, the generalized `components_missing_subtype`
classifier-gap check, and the parquet HTML cache/fetch helpers. The now-dead `.gitignore` rule was
removed (commit `c34f7e3`). Also banked earlier on this branch: `bench_parse.py` logs to
`tests/benchmarks/results.jsonl` + saves `.prof` dumps (`snakeviz` added to the dev group), and the
stale fixture glob was fixed.

### 2026-06-05 — bucket A: absorb demos (decision 1 = option a, full absorb)

Root cause was worse than "typer/polars missing": the wheel ships only `WebSearcher/` (sdist
`only-include` adds `scripts`, but the wheel does not), so the `scripts.demo_*:app` console entry
points are unimportable on a wheel install *and* pull non-runtime deps. Both are fixed by moving the
demos into the shipped package.

Verified before writing: `import WebSearcher` loads neither polars nor typer; `download_locations`,
`load_soup`, `parse_serp`, `Extractor`, `SearchEngine` are all public; `detect_chrome_version` lives
at `WebSearcher.search_methods.selenium_searcher`. The four user demos use `polars` only to print a
results table (and `demo_locations` to filter the geotargets CSV) — both replaceable with stdlib.

Implementation:
- New `WebSearcher/demo.py` (runtime-deps-only): `parse`, `search`, `headers`, `locations` runners +
  a tiny stdlib table printer (replaces polars) + an `argparse` CLI (`python -m WebSearcher.demo
  <cmd>`) and a `search_cli` entry. Standardized on `se.parse_serp()` / `se.parsed.results`.
- Repointed `[project.scripts]`: `demo-search` -> `WebSearcher.demo:search_cli`; dropped the
  `demo-searches` console script (that bulk corpus generator stays a `scripts/` dev tool, kept per
  bucket C, and its entry point was already wheel-broken).
- Dropped `scripts` from the sdist `only-include` (its only rationale was the now-moved entry points).
- Deleted the four absorbed scripts (`demo_parse`, `demo_search`, `demo_search_headers`,
  `demo_locations`); `demo_searches` stays.
- Plan-031 loose end resolved: the geotargets download already lives in the package as
  `ws.download_locations`, so the locations demo reuses it (no duplication).
- Entry point finalized as a single unified `ws-demo` -> `WebSearcher.demo:main` (replacing the
  interim `demo-search` -> `search_cli`, now removed), so all four subcommands run as
  `ws-demo <cmd>` without `python -m`. Chose `ws-demo` over a bare `demo`/`ws` to avoid the quiet
  last-one-wins console-script collision risk of a generic name. README updated.

### 2026-06-05 — buckets C, D, B

**Bucket C (consolidate keepers).** Salvaged `diff_parsers.py`'s reusable kernel — the bz2 corpus
loader and `serp_label` — into `scripts/_common.py` as `load_serp_records` / `serp_label`, and
rewired the three kept corpus scripts (`compare_drop_signatures`, `profile_fixture_corpus`,
`verify_*`) onto it (dropping each one's private loader and the dead pre-consolidation glob fallback
in `profile_fixture_corpus`). Generalized `verify_drops.py` -> `verify_corpus.py`: dropped the
plan-032-specific `PLAN032_DROPS`/`REQUIRED_LAYOUTS` constants and the vacuous pair-carrier check;
it's now a generic integrity guard (unique ids, every record noted, every record yields a
`main_layout` and >=1 result). All three run green over the 80-record corpus.

**Bucket D (retire one-offs).** Deleted `parsed_to_csv`, `build_fixture_corpus`, `condense_fixtures`,
`dump_ai_overview_html`, `inspect_ai_overview_structure`, and `diff_parsers` (salvaged first). Fixed
two stale README spots: the `condense_fixtures` fixtures workflow (now points at the consolidated
corpus + `docs/guides/fixture-corpus.md`) and a snapshot-test example citing a dropped serp_id
(`45b6e019bfa2` -> `4f4d0fed0592`, verified to match one test).

**Bucket B (skills).** Per decision, built all four as new local skills under `.claude/skills/`
(gitignored, the established pattern here): `serp-view`, `corpus-curate`, `parser-regression`,
`parse-bench`. Discovered the repo already has overlapping/stale skills (`reparse`, `compare-parsed`
use the old list API; `reparse`/`parser-update` reference the retired `serps-v*` glob) — left a TODO
to reconcile and de-stale them in a follow-up rather than expand scope here.

### 2026-06-05 — folded demo_searches into the package (reclassified from bucket C)

Reversed the bucket-C "keep in scripts/" call for `demo_searches.py`: it was the last demo still
importing typer/polars (broken on a clean install, never shipped in the wheel), and structurally
it's just the `search` runner looping over a curated query battery. Absorbed it into
`WebSearcher/demo.py` as `ws-demo searches` (the `QUERIES` battery + CAPTCHA-retry + jittered
`--delay` moved in; typer->argparse, polars->stdlib table; factored a shared `_add_engine_args`),
and deleted the script. `ws-demo` now exposes `parse|search|searches|headers|locations`, and no demo
remains outside the package. (`demo_screenshot.py` stays in `scripts/` — it's a parser-debug tool,
not a demo.)

### 2026-06-05 — split the crowded `demo.py` into a `WebSearcher/demos/` package

The single ~400-line `WebSearcher/demo.py` had grown to hold all five runners, the QUERIES battery,
the display/path helpers, and the whole argparse CLI. Split it into a package, one concern per
module, with no behavior change:

- `demos/_common.py` — shared stdlib display/path helpers (`_print_results_table`, `_default_data_dir`).
- `demos/parse.py`, `search.py`, `headers.py`, `locations.py` — one runner each, with that runner's
  own constants/helpers alongside it (`QUERIES`/`_chrome_version` in `search`, `MODIFIED_HEADERS` in
  `headers`, `_find_location` in `locations`).
- `demos/cli.py` — the argparse plumbing (`_add_engine_args`/`_add_search_args`/`_run_search`/`main`).
- `demos/__init__.py` — re-exports `main` + the five runners + `QUERIES` via `__all__`.
- `demos/__main__.py` — `python -m WebSearcher.demos`.

The one wired change the rename forced (the "unless needed" part of the ask): the entry point moved
`WebSearcher.demo:main` -> `WebSearcher.demos:main` in `pyproject.toml`, and the `_chrome_version`
import deepened a level (`..search_methods`). The **user-facing CLI is byte-identical** — `ws-demo`
plus every subcommand's `--help` diffs clean against a pre-split baseline. Verified: no `polars`/`typer`
pulled in, `python -m WebSearcher.demos` runs, offline `ws-demo parse` works on stored HTML, ruff
clean, and the full suite stays green (326 passed, 80 snapshots). Updated the `pyproject.toml` sdist
comment and the CHANGELOG `[Unreleased]` demos line to say `WebSearcher.demos`.

### 2026-06-05 — verified the kept (bucket C) scripts; fixed two broken by the selectolax rewrite

Exercised all 10 remaining `scripts/` against stored data to confirm the "Keep" disposition actually
holds post-026. Eight run green as-is: `_common`, `verify_corpus`, `profile_fixture_corpus`,
`compare_drop_signatures`, `bench_parse`, `reparse_demo`, `show_parsed`, and `show_serp` (the last uses
a *standalone* bs4 for overlay stripping — a dev dep, never fed into the WS pipeline — so the selectolax
switch didn't touch it).

Two were silently **broken by the parallel selectolax rewrite** (plan 026) because they feed `bs4`
objects into `Extractor`/`ClassifyMain`, which now expect selectolax nodes — the audit had kept them
without re-testing against the new backend:

- `survey_ai_overviews.py` — `bs4.BeautifulSoup(html, "lxml")` -> `Extractor` blew up on
  `soup.css("*")` (`TypeError: 'CSS' object is not callable`). Ported the loader to `ws.make_soup` and
  the `summarize()` traversal to the package's own `_slx` helpers (`get_text`, `class_tokens`,
  `subtree_css`/`subtree_first`) — the faithful bs4-equivalents the parsers already use. Now reports
  AI-overview structure again (e.g. 22 overviews in `demo-ws-v0.6.10a0`).
- `demo_screenshot.py` — entire `highlight_components` was bs4 API (`find_all(True)`, item-assign,
  `copy.copy`, `new_tag`, `head.append`); `ws.make_soup` now returns a `LexborNode` with none of those.
  Reworked onto selectolax mutation (`node.attrs[...]=`, `del node.attrs[...]`, `css`/`css_first`),
  re-parse the tagged HTML for the classify-on-a-copy step instead of `copy.copy`, and inject the
  `<style>` overlay by string-splice on `</head>` (the function returns HTML anyway). Verified in
  isolation: classifies 13 components on a stored SERP, emits the `<style>` block and `data-ws-rank`
  targets, and strips the temporary `data-ws-id` tags. (selenium screenshot step unchanged.)

ruff clean on both. Net: every kept script now runs. Still open (tracked separately in TODO): the
`.claude/skills` reconciliation, and the README still pointing end users at the dev-only
`scripts/show_parsed.py` (typer+polars, never shipped) in the demo walkthrough.

### 2026-06-05 — moved `reparse_demo.py` into the `/parser-regression` skill

Audited which kept scripts are referenced by which existing skills: every one except
`survey_ai_overviews.py` backs at least one skill, and `reparse_demo.py` is a clean 1:1 with
`parser-regression` (no other skill or user touches it). Since `.claude/skills/` is gitignored, a
script bundled there *persists across `git checkout`* — exactly what a cross-checkout regression
harness wants (the harness stays constant while the parser code under test changes per branch). So
`reparse_demo.py` moved out of `scripts/` (tracked) into `.claude/skills/parser-regression/` (local).
Changes: `DATA_DIR` is now cwd-relative `Path("data")` (the skill runs from the repo root) instead of
`__file__`-relative; the SKILL.md points at the bundled path and its stale `scripts/demo_searches.py`
reference (deleted/absorbed into `ws-demo searches`) is fixed. Verified it still reparses the demo
corpus from the new location (15 SERPs, 0 errors). `scripts/` is down to 9 files.

Noted for the skills-reconciliation follow-up: `show_parsed.py` is the shared workhorse (4 skills:
compare-parsed, parser-update, reparse, serp-view) so it can't collapse into one skill; `bench_parse.py`
is the other clean 1:1 (parse-bench) and a future move candidate; `survey_ai_overviews.py` is the lone
script no skill references.

### 2026-06-05 — skills reconciliation done in plan 038

The follow-up above is handled by [plan 038](038-consolidate-skills-absorb-scripts.md): the 8 skills
collapse to 4 (`serp-inspect`, `compare-parsed`, `corpus-curate`, `parse-bench`) and `scripts/` sheds
to a single file (`survey_ai_overviews.py`). The `show_parsed.py`-can't-collapse blocker dissolved by
combining the four overlapping inspection skills and replacing the script with a package-native
`ws-demo show`; `bench_parse.py` moved into `parse-bench` as predicted.

## Retrospective

Shipped via PR #152 (merged into `feature/v0.9.0`). The audit's core bet held: most of `scripts/` was
either user demos that belonged in the package or maintainer workflows that belonged in skills. The one
disposition that flipped during implementation was `bench_parse.py` — kept tracked, then folded into the
package as `WebSearcher.bench` rather than a gitignored skill, because it's the perf gate that writes to
the tracked `tests/benchmarks/`. Net: `scripts/` removed entirely. The skills reconciliation is plan 038
(this plan was renumbered 033 → 037 to clear a collision with the kp-wholepage plan 033 the version
branch created in parallel).
