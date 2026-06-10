---
id: 48
slug: captcha-exit-on-sorry-redirect
status: draft
branch:
created: 2026-06-09T23:06:21-07:00
concluded:
pr:
---

# Detect CAPTCHA via the /sorry/ redirect URL and exit early

## Problem

CAPTCHA detection (`utils.has_captcha`) only walks the **HTML text** for the literal
`"CAPTCHA"`. When Google challenges a request it redirects to
`https://www.google.com/sorry/index?continue=<original>&q=<token>`, and the browser backends
(`SeleniumDriver`, `PatchrightSearcher`, `ZendriverSearcher`) wait for `#search`, which never
appears on that page. The wait times out, `send_request` returns **empty HTML** with
`response_code` 0, and `response_output.url` is never updated to the redirect target. The result:

- `has_captcha` sees nothing (empty HTML), so `features["captcha"]` stays `False`.
- The `ws-demo searches` loop's CAPTCHA guard never fires, so it keeps issuing requests into a
  block instead of backing off or stopping — exactly when it should stop.

Surfaced while evaluating browser backends (plan 039): both plain Playwright and headless
patchright land on `/sorry/index` on the first query, and the loop kept going with empty results.

## Plan

1. **Capture the final URL even on failure.** In each browser backend's `send_request`, set
   `response_output.url` to the live `current_url` / `page.url` *before* the `#search` wait (or in
   the `except`/`finally`), so a redirect is recorded regardless of whether the wait succeeds.
   Capture whatever HTML is present on timeout too, so the `/sorry/` page is saved rather than
   discarded.
2. **Add a URL-based CAPTCHA signal.** A helper (e.g. `utils.is_sorry_redirect(url)`) matching
   `^https?://(www\.)?google\.com/sorry/` — robust even when HTML capture is empty. Fold it into
   the feature extraction so `features["captcha"]` is `True` when either the HTML text marker or
   the redirect URL is present. (The extractor will need the response URL threaded in alongside
   the HTML; check the `parse_serp` path.)
3. **Exit early in the loop.** In `demos/search.py::searches`, treat a detected CAPTCHA as a stop
   condition (the current 5-min-wait-and-retry-once is fine; the point is it must actually fire).
   Consider a hard stop after the single retry still being blocked (already present) and make sure
   the URL signal feeds the same guard.
4. **Test fixtures.** Add a saved `/sorry/index` page fixture and assert `has_captcha` /
   `is_sorry_redirect` flag it; assert a normal SERP does not false-positive.

## Evidence

Reproduce from a blocked backend (plain playwright is reliably blocked on the first query):

```bash
uv sync --group spike   # plan-039 PoC deps; or use selenium once headless/IP triggers a block
uv run python - <<'PY'
from patchright.sync_api import sync_playwright
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(user_data_dir="/tmp/ws-sorry", channel="chrome", headless=True, no_viewport=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.google.com/search?q=why+is+the+sky+blue", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    print("final url:", page.url)              # -> https://www.google.com/sorry/index?continue=...
    print("/sorry/ in url:", "/sorry/" in page.url)
    print("CAPTCHA in html:", "CAPTCHA" in page.content())
    ctx.close()
PY
```

Current code: `WebSearcher/utils.py::has_captcha` (HTML-text only),
`WebSearcher/extractors/extractor_serp_features.py:56` (sets `features["captcha"]`),
`WebSearcher/demos/search.py:158-165` (loop guard), and the three browser backends'
`send_request` in `WebSearcher/search_methods/`.

## Out of scope

- Solving headless/container CAPTCHA evasion (needs a real display or residential proxy +
  anti-detect headless) — this plan only makes detection reliable and stops the loop early.
- The browser-backend migration itself (plan 039 follow-up).
