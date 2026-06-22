---
id: 51
slug: drop-extra-searchers
status: active
branch: feature/v0.11.0
created: 2026-06-21T17:15:10-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/177
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
  (tracked elsewhere in the downstream collection tooling).
- Any change to the `requests` or `patchright` behavior beyond making patchright the default.

## Log

- **2026-06-21** — Implemented on `feature/v0.11.0` (worktree). PR
  [#177](https://github.com/gitronald/WebSearcher/pull/177).
  - **configs.py:** dropped `SeleniumConfig`/`ZendriverConfig`; `SearchMethod` trimmed to
    `REQUESTS`/`PATCHRIGHT` with the `None` default now `PATCHRIGHT`; `SearchConfig` lost the
    `selenium`/`zendriver`/`playwright` fields and defaults to `PATCHRIGHT`.
  - **searchers.py:** removed the selenium/zendriver/playwright imports, kwargs, config dict
    entries, type-union arms, and `init_driver` branches; default `method` arg → `PATCHRIGHT`.
  - **Deleted** `selenium_searcher.py`, `zendriver_searcher.py`, and the `PlaywrightSearcher`
    subclass. Inlined the now-orphan `_start_playwright` seam into `PatchrightSearcher.init_driver`
    and refreshed the module's "proof-of-concept" framing (patchright is now the primary backend).
  - **pyproject.toml / uv.lock:** promoted `patchright>=1.60.1` to runtime, removed
    `undetected-chromedriver` + `selenium`, dropped the `spike` group and the dev `setuptools`
    distutils shim, trimmed `[tool.pyrefly]` ignore-missing-imports to just `patchright`, and
    bumped the version to `0.11.0a0` (both `pyproject.toml` and `WebSearcher/__init__.py`).
  - **Demos:** `cli.py` default `patchright`, choices `["requests", "patchright"]`, and removed
    the dead selenium-only flags (`--use-subprocess`, `--version-main`, `--driver-executable-path`);
    `search.py` simplified `_engine_kwargs`, removed `_chrome_version`, defaulted to `patchright`.
  - **Tests:** `test_models.py` swapped the `SeleniumConfig` cases for `PatchrightConfig` and
    flipped the default/method assertions to patchright; `test_search_methods.py` dropped the
    selenium/zendriver sections (now-deleted imports), keeping the patchright failure-path tests.
    Full suite green (534 passed, 87 snapshots), ruff + format clean, pyrefly 0 errors.
  - **Docs:** README tagline (`selenium` → `patchright`), a `0.11.0` Recent Changes entry, a
    `patchright install chromium` install step, the Initialize-Collector example switched to
    `patchright_config`, the minimal pipeline pinned to `method="requests"`, and the Xvfb section
    rewritten for the single browser backend; CHANGELOG `[Unreleased]` Breaking entry. Also touched
    `logger.py` (dropped the uc logger levels), `__init__.py` and `models/data.py` comments, and
    generalized a private-repo reference in this plan's Out-of-scope note.

- **2026-06-21 (follow-up)** — Post-merge polish, live validation, and an Xvfb block-rate
  investigation.
  - **Polish commits:** README quickstart now leads with the patchright default instead of
    `requests` (345d3dc); dropped the now-pointless `ws-demo --headless` flag and its dead
    `_engine_kwargs`/param plumbing — the browser backend must run headed, so the flag only
    surfaced a path search engines reliably block (5b4a2aa); prerelease bump
    `0.11.0a0` → `0.11.0a1` via `stanza release prerelease` (2bb3b3e).
  - **Live validation:** `ws-demo searches` full battery on WSL2+WSLg (real display, 30s
    spacing) cleared **48/48 queries, 0 CAPTCHA, 1177 components** across all 16 component
    types — the patchright-default setup holds up end to end.
  - **Xvfb block-rate question:** does headed-under-Xvfb block more than a real display?
    Interleaved single queries (`--no-ai-expand`, distinct query each, fresh temp profile)
    across both displays at the same current IP state: at ~10s spacing WSLg cleared 4/4 and
    Xvfb 3/4 (one `/sorry/`); at **30s spacing both cleared 10/10 — no measurable Xvfb
    penalty.** The earlier Xvfb blocks (an immediate `/sorry/` on the first battery query and
    one lone single) were intermittent challenges tracking IP-warmth + tight spacing, not the
    display. Confirms plan 049's Finding #3 with stronger evidence (n=10/display vs 049's n=2).
  - **Fingerprint check (local, no network):** WebGL renderer **identical** under both
    displays — `ANGLE (Microsoft, D3D12 (Intel UHD 770))` — because WSL2 passes the GPU
    through to Chrome regardless of which X display it attaches to, so there is **no
    software-renderer (SwiftShader) tell** under Xvfb on WSL2 (the milder signal 039/049
    anticipated does not occur here). Only deltas: `requestAnimationFrame` cadence (~30 fps
    WSLg vs ~18 fps Xvfb) and window/screen geometry — neither moved the block rate.
  - **Incidental:** patchright launches Chrome with `--no-sandbox` by default
    (`PatchrightSearcher.init_driver` leaves `chromiumSandbox` unset), tripping Chrome's
    "unsupported command-line flag" infobar on every headed launch — not exposed to page JS
    (weak/no bot signal) but a hygiene/security deviation.
  - Repro (interleaved, 30s apart): alternate
    `uv run ws-demo search "<q>" patchright --no-ai-expand` (real display) with
    `env -u DISPLAY xvfb-run -a --server-args="-screen 0 1920x1080x24" uv run ws-demo search
    "<q>" patchright --no-ai-expand` (Xvfb).

  **Net:** Xvfb is functional *and* block-rate parity with a real display at controlled
  spacing; the standing blocker remains IP reputation/volume.

  **Next steps (for next time):**
  - **Proxies are the real lever** — IP reputation/volume is the dominant blocker regardless
    of display or backend; for live collection at scale, route through residential/mobile
    proxies. Everything else is secondary.
  - **Respect spacing** — keep >=30s between queries (the `searches` 30s default held up;
    tighter raised the block rate), and don't burn the IP with rapid back-to-back testing.
    Let the IP cool between heavy runs.
  - **Xvfb is safe** on no-display hosts (server/CI/container) — no need to avoid it; the same
    IP/spacing discipline applies.
  - **Optional hardening:** default `chromiumSandbox=True` for the patchright backend to drop
    the `--no-sandbox` infobar — but verify the sandbox initializes in the target env first
    (containers/CI may need user namespaces; that's why playwright leaves it off).
  - **Better block-rate testing:** interleaved A-B harness, fixed spacing, n>=10 per
    condition — small-n is noisy (a one-off 1/4 looked like a signal and wasn't). A
    spacing/volume sweep would map a safe request rate.

- **2026-06-21** — Kicked off the *full* `ws-demo searches` battery under Xvfb (single reused
  session, AI-expand on, all component types, 30s spacing) to stress the single-session/cascade
  scenario flagged above — the harder test the per-query A-B runs deliberately avoided. At the
  20-min check: **33/48 cleared, all HTTP 200, 0 CAPTCHA, 886 components — no cascade so far.**
  Output in `data/xvfb-searches-test/` (local, gitignored).

- **2026-06-22** — **Battery completed and confirmed.** The reused single session held the
  whole way through: **48/48 queries cleared, all HTTP 200, 0 CAPTCHA, 1202 components across
  22 component types**, over a ~30.5-min run (05:21–05:52, patchright `0.11.0a1`). **No
  cascade** — the harder single-session/AI-expand scenario passes end to end under Xvfb, not
  just the per-query A-B runs. The only `unknown` components were 3 travel widgets (flights/
  hotels queries) — a pre-existing parser-coverage gap, not a block or Xvfb regression.
  **Net:** the single-session Xvfb concern is closed — patchright-under-Xvfb has block-rate
  parity *and* session durability with a real display at >=30s spacing; the standing blocker
  remains IP reputation/volume (proxies are the real lever).
