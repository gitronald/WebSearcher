---
id: 51
slug: drop-extra-searchers
status: active
branch: feature/v0.11.0
created: 2026-06-21T17:15:10-07:00
concluded:
pr:
---

# Drop all search backends except patchright and requests

## Background and rationale

WebSearcher ships five `method=` backends: `requests`, `selenium` (undetected-chromedriver),
`zendriver`, `patchright`, and `playwright`. The browser evaluation in plan 039
([[browser-automation-alternatives]], PR #166) ran a four-way battery and a follow-up, with a
clear outcome per backend:

- **patchright** — *recommended.* Equal stealth (0 blocks/18 queries), the only silent +
  fully deterministic teardown, a sync API that drops into the existing contract, healthiest
  maintenance, permissive Apache-2.0, and runs the system Chrome channel. Cost: 143 MB wheel.
- **selenium + undetected-chromedriver** — works, but the dep is abandoned upstream, is the
  heaviest part of the runtime tree, needs a `use_subprocess` workaround to launch on Python
  3.14, and is GPL-3.0. Superseded by patchright.
- **zendriver** — works, active fork, but async-only (event-loop shim), AGPL-3.0, with a 3.14
  wart. Named only as patchright's *fallback if wheel size ever mattered* — it doesn't here.
- **playwright** (plain, no stealth patch) — **18/18 blocked** in the follow-up; the stealth
  patch is load-bearing, so plain playwright is not viable.
- **requests** — legacy pure-HTTP path; increasingly blocked for live collection but kept for
  reparse, lightweight use, and as the no-browser option.

Plan 049 ([[xvfb-virtual-display]], PR #175) then confirmed patchright runs headed on a
no-display host via Xvfb with parse parity, so patchright covers the headless-server use case
that selenium was kept around for. With patchright validated as the single browser backend and
`requests` as the no-browser path, the other three backends are redundant maintenance and
dependency weight. This plan removes them and makes **patchright the default**.

This is plan 039's green-lit migration follow-up. Note one deliberate divergence: 039 floated
keeping `method=selenium` for "one deprecation cycle" — here we do a **clean removal** in a
single minor (0.11.0) instead, since `requests` remains as a no-browser fallback and the
migration to patchright is a one-line `method=` change.

## Plan

Target version **0.11.0** (minor; breaking for the removed methods). Integration branch
`feature/v0.11.0`.

1. **Trim the method/config surface** (`WebSearcher/models/configs.py`):
   - `SearchMethod` enum: keep `REQUESTS` and `PATCHRIGHT`; remove `SELENIUM`, `ZENDRIVER`,
     `PLAYWRIGHT`. Change `SearchMethod.create()`'s `None` default from `SELENIUM` to
     `PATCHRIGHT`.
   - Remove `SeleniumConfig` and `ZendriverConfig`; drop the now-stale "PoC ... requires the
     `spike` dep group" note from `PatchrightConfig`.
   - `SearchConfig`: remove the `selenium`, `zendriver`, and `playwright` fields; change
     `method` default `SELENIUM` -> `PATCHRIGHT`.

2. **Trim the dispatcher** (`WebSearcher/searchers/searchers.py`): drop the selenium/zendriver/
   playwright imports, the type-union arms, and their `init_driver` branches; default
   `__init__` `method` arg `SELENIUM` -> `PATCHRIGHT`.

3. **Delete the dropped searcher modules**: `selenium_searcher.py`, `zendriver_searcher.py`,
   and the `PlaywrightSearcher` subclass in `patchright_searcher.py:198`. Keep
   `patchright_searcher.py` and `requests_searcher.py`.

4. **Dependencies** (`pyproject.toml` + `uv lock`):
   - Promote `patchright>=1.60.1` from the `spike` group into runtime `dependencies`.
   - Remove `undetected-chromedriver` and `selenium` from runtime; remove the `spike` group
     (now only `playwright`/`zendriver`, both dropped); drop the dev-group `setuptools`
     distutils shim (it existed only for undetected-chromedriver on 3.12+).
   - Audit the `[tool.*]` config that lists `patchright`/`zendriver` modules; re-lock with
     `uv lock`.
   - **Post-install note for docs:** patchright needs its browser binary
     (`patchright install chromium`) — a new required step pip can't run automatically.

5. **Demos** (`WebSearcher/demos/`): in `cli.py` set the `method` default to `patchright` and
   the `choices` to `["requests", "patchright"]`; in `search.py` drop the selenium/zendriver/
   playwright arms of `_engine_kwargs` and remove the selenium-only `_chrome_version` header
   helper (it imports `detect_chrome_version` from the deleted `selenium_searcher`).

6. **Tests**: update `tests/test_search_methods.py` and `tests/test_models.py` to the trimmed
   method/config set (drop selenium/zendriver/playwright cases; assert the new patchright
   default). Run the full suite + ruff + pyrefly.

7. **Docs** (the "update docs accordingly" deliverable):
   - **README** — rewrite the backend mentions in the new "Running on a headless server
     (Xvfb)" section (currently "`selenium` -- the default -- plus optional `patchright`/
     `zendriver`") to "patchright (the default) and requests"; update Getting Started / Usage
     install + `method=` examples; add the `patchright install chromium` step.
   - **CHANGELOG** — a `0.11.0` **Breaking** entry (methods removed, default changed, deps
     swapped, browser-binary install step).
   - Audit `CLAUDE.md` and any `ws-demo`/usage references for the dropped methods.

## Breaking changes and migration

- `method="selenium"`, `"zendriver"`, and `"playwright"` are removed — constructing a
  `SearchEngine` with them now raises (the enum no longer defines them). **Migration:** use
  `method="patchright"` (now the default) and run `patchright install chromium` once.
- The **default** backend changes from `selenium` to `patchright`, so a bare
  `ws.SearchEngine()` launches patchright instead of undetected-chromedriver.
- `SeleniumConfig`/`ZendriverConfig` and the `selenium_config`/`zendriver_config`/
  `playwright_config` kwargs are gone.
- Install footprint: drops `selenium` + `undetected-chromedriver`, adds `patchright`
  (~143 MB, bundles the node driver). `requests` is unchanged and remains the no-browser path.

## Out of scope

- IP reputation / proxies — the dominant live-collection blocker regardless of backend
  (tracked elsewhere; see the SearchAudits migration discussion).
- Any change to the `requests` or `patchright` behavior beyond making patchright the default.
