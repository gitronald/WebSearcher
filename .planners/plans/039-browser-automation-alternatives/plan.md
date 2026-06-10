---
id: 39
slug: browser-automation-alternatives
status: active
branch: feature/v0.10.0-browser-backend
created: 2026-06-05T17:46:22-07:00
concluded:
pr:
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
