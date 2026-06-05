---
status: active
branch: feature/v0.9.0-script-cleanup
created: 2026-06-05T09:53:50-07:00
completed:
pr:
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
