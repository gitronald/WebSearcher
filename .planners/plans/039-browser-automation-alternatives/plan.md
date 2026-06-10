---
id: 39
slug: browser-automation-alternatives
status: active
branch: feature/v0.10.0-browser-backend
created: 2026-06-05T17:46:22-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/166
---

# Investigate browser-automation alternatives to undetected_chromedriver

## Problem

The selenium backend is built on `undetected_chromedriver` (uc), which carries recurring friction:

- Emits a `multiprocessing.resource_tracker` "leaked semaphore" warning at shutdown (uc's
  teardown races interpreter exit; relies on `SeleniumDriver.__del__`, not a deterministic close).
- Predates Python 3.14 support; couples to the installed Chrome **major** version.
- Heaviest part of the runtime dep tree (`selenium` + `undetected-chromedriver` + `websockets`).

Goal: a brief evaluation of whether a different backend is cleaner, stealthier, and/or lighter —
**not** a commitment to migrate.

## Candidates

- **Playwright** (sync API) — bundled/pinned browsers, deterministic context lifecycle, headless;
  stealth via `playwright-stealth` or the `patchright` fork.
- **nodriver** — uc author's successor; pure-async CDP, no selenium/webdriver; built to fix uc's
  detection and teardown issues.
- **patchright** — drop-in "undetected" Playwright.
- **Plain Selenium 4 + manual stealth** — baseline for comparison.

## Evaluation criteria

1. Detection / CAPTCHA-block rate on live Google SERPs (the metric that actually matters).
2. Teardown cleanliness — deterministic close, no leaked-semaphore warning.
3. Python 3.14 support and dependency weight.
4. Fit behind the existing searcher contract (`SeleniumDriver`: `init_driver` /
   `send_request(SearchParams) -> ResponseOutput` / `cleanup`) and AI-overview expand (click) parity.
5. Maintenance / activity.

## Approach

- Spike the top one or two candidates as a new `SearchMethod`, mirroring the `SeleniumDriver`
  interface so `parse_serp` output is unchanged.
- Run the demo query battery (`ws-demo searches`) across backends; compare block/CAPTCHA
  rate, HTML/parse parity, and shutdown noise.
- Record findings in the Log; recommend one backend and note migration cost.

## Deliverable

A short findings writeup plus a recommendation, and a throwaway proof-of-concept searcher for the
leading candidate behind `method=`. Actually migrating off uc (and any dep changes) is a separate,
follow-up plan if green-lit.

## Out of scope

- The `requests` backend; the full migration itself.
- A quick interim mitigation (deterministic `driver.quit()` before shutdown to quiet the semaphore
  warning) is independent of this evaluation and can land on its own.

## Log

### 2026-06-09 — PoC backends, battery evaluation, recommendation

**Candidate triage.** nodriver disqualified itself before any stealth testing:

- nodriver >= 0.48.0 (incl. latest 0.50.3) is **import-broken on every Python** — the published
  wheels ship a non-UTF-8 byte (a latin-1 `±` in a `cdp/network.py` comment, plus CRLF endings),
  a `SyntaxError` at `import nodriver`. Broken since 2025-10-29 and unfixed.
- The last importable release (0.46.2, 2025-09-06) emits a PEP 765 `SyntaxWarning`
  (`'continue' in a 'finally' block`) on Python 3.14, which is slated to become an error.
- Single maintainer; issue tracker periodically wiped (8 open issues, oldest 2026-03-31, on a
  4.3k-star repo) — the documented motivation for the **zendriver** fork (cdpdriver/zendriver,
  0.15.3, multi-maintainer, deterministic `await browser.stop()` teardown). zendriver was
  substituted as the CDP-lineage candidate; it inherits the PEP 765 warning but is otherwise
  clean on 3.14.

playwright + playwright-stealth was not spiked: its JS-injection stealth lineage is itself
fingerprinted by modern detection and is dominated by patchright, which patches the driver
(`Runtime.enable` leak, console leak, flag leaks) instead of injecting scripts.

Baseline status: undetected-chromedriver is effectively abandoned (last release 3.5.5,
2024-02-17; ~1,100 open issues; the author's attention moved to nodriver). New failure found
during this work: on **Python 3.14 + Linux** the `multiprocessing` default start method changed
fork -> forkserver, and uc's `start_detached` launch path (default `use_subprocess=False`)
re-imports `__main__` in the child and crashes at startup — the selenium backend now requires
`use_subprocess=True` to launch at all.

**PoC.** Two throwaway backends added behind `method=`, both mirroring the `SeleniumDriver`
contract (`init_driver` / `send_request(SearchParams) -> ResponseOutput` / `cleanup`), with
config classes, `SearchEngine` dispatch, and `ws-demo` wiring:

- `WebSearcher/search_methods/zendriver_searcher.py` — async CDP wrapped in a dedicated event
  loop (sync facade).
- `WebSearcher/search_methods/patchright_searcher.py` — sync Playwright API, persistent context
  on the system-Chrome channel (patchright's documented stealth baseline).

Deps live in a PEP 735 `spike` dependency group (not shipped in the wheel); the searcher modules
lazy-import so the package works without them. The AI-overview expand clicks were ported from
XPath to CSS selectors (`div[jsname="rPRdsc"][role="button"]`, `div.trEk7e[role="button"]`).

**Battery.** 18 queries (types: ad, general, knowledge, knowledge_panel, local_results,
top_stories), 30s jittered delay, headed, `ai_expand` on, system Chrome 148, residential IP,
one browser session per backend:

```bash
uv sync --group spike
uv run ws-demo searches selenium --use-subprocess --types ad general knowledge knowledge_panel local_results top_stories --data-dir data/plan039-selenium
uv run ws-demo searches zendriver --types ad general knowledge knowledge_panel local_results top_stories --data-dir data/plan039-zendriver
uv run ws-demo searches patchright --types ad general knowledge knowledge_panel local_results top_stories --data-dir data/plan039-patchright
```

| Criterion | selenium + uc | zendriver | patchright |
|---|---|---|---|
| Blocks / CAPTCHAs (18 queries) | 0 | 0 | 0 |
| HTML returned | 18/18 | 18/18 | 18/18 |
| Parsed results/SERP (mean) | 27.6 | 28.7 | 29.6 |
| Parse parity | baseline | identical component mix | identical component mix |
| AI-overview expand | works | works | works |
| Teardown | needs `use_subprocess=True` on 3.14; urllib3-muting workaround | deterministic `await stop()`; one benign warning on `__del__` path | silent, deterministic |
| Python 3.14 | crashes at launch by default | OK (inherited SyntaxWarning) | OK |
| Dependency closure | 18 dists, 27 MB | 8 dists, 9 MB | 4 dists, 143 MB (bundles node driver) |
| API fit | sync | async-only (event-loop facade) | sync, drop-in |
| Maintenance | abandoned | active community fork | very active, tracks playwright ~2 wks |
| License | GPL-3.0 | AGPL-3.0 | Apache-2.0 |

Per-query component-type distributions were near-identical across backends; the deltas
(ad counts, top_stories presence, volatile knowledge-panel queries) match normal SERP variance,
not backend artifacts. Detection on this battery is a three-way tie — consistent with outside
reports that Google blocks are driven mainly by IP reputation and rate, not these frameworks'
remaining leaks.

**Recommendation: patchright.** Equal stealth on the battery, the only silent + fully
deterministic teardown, a sync API that drops into the existing contract with no event-loop
shim, the healthiest maintenance story (version-locked to upstream Playwright), permissive
Apache-2.0 (vs zendriver's AGPL-3.0), and it runs the system Chrome channel so no bundled
browser download is needed. Its main costs: a 143 MB wheel (bundled node driver) and weaker
stealth in container/datacenter environments (community reports) — acceptable for this tool's
researcher-desktop usage. zendriver is the fallback if wheel size ever matters more: 9 MB,
no driver process at all, but async-only, AGPL, and one inherited 3.14 wart.

Migration (follow-up plan if green-lit): promote `PatchrightSearcher` to the default
`method=`, drop `selenium` + `undetected-chromedriver` (and the `setuptools` distutils shim)
from runtime deps, retire `use_subprocess`/`version_main`/`driver_executable_path` config, and
keep `SeleniumDriver` behind `method=selenium` for one deprecation cycle.

### 2026-06-09 — follow-up checks: plain playwright, and headless

Two questions raised after the first pass; both answered empirically on the same machine/IP
where the four-way battery ran clean, so the only variable is the driver.

**Does the stealth patch actually matter, or is plain Playwright enough?** Added a
`PlaywrightSearcher` (subclass of `PatchrightSearcher`, only swaps the `sync_playwright`
import — `method=playwright`) and ran the same 18-query battery:

| | patchright | plain playwright |
|---|---|---|
| Blocks (18 queries) | 0 | **18** |
| HTML returned | 18/18 | 0/18 (all empty) |
| Final page | SERP | `google.com/sorry/index` reCAPTCHA wall |

Plain Playwright is redirected to the "unusual traffic" reCAPTCHA on the **first** query and
never recovers. So patchright's driver patches (`Runtime.enable`/console/flag leaks) are doing
real work against Google here — plain Playwright is **not** sufficient, and switching to it
would not reduce deps anyway (patchright *is* playwright-python with a patched driver; identical
`pyee`/`greenlet`/bundled-node-driver tree, same ~143 MB). This rules out the
"plain-playwright, lighter" option and reinforces patchright over zendriver/selenium.

**Can patchright run headless?** It launches and runs headless fine, but Google **blocks it**:
default headless Chrome advertises `HeadlessChrome/148.0.0.0` in the UA, and the request lands on
the same `google.com/sorry/index` reCAPTCHA wall (`response_code` 0, empty HTML). So headless
defeats patchright's stealth advantage on Google — this backend (like the current selenium one)
needs **headed** operation. Headless is fine for offline/non-Google targets, not for live SERP
collection. (Captcha-evasion in headless/container environments is the documented weak point for
all these frameworks; not solvable at the driver layer alone — it needs a real display or a
residential-proxy + anti-detect-headless setup, out of scope here.)

**Observed gap (-> follow-up plan):** when Google serves `/sorry/`, the backends time out
waiting for `#search`, return empty HTML, and never set `response_output.url` to the redirect,
so `has_captcha` (HTML-text only) sees nothing and the `searches` loop keeps hammering. A robust
early-exit should key off the **final URL** matching `^https?://www\.google\.com/sorry/` (and set
the captcha flag / capture HTML even on the wait timeout). Carved out as its own plan since it
changes production collection behavior across all browser backends, independent of the uc
migration.
