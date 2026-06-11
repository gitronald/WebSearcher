---
id: 48
slug: captcha-exit-on-sorry-redirect
status: done
branch: feature/v0.10.0-captcha-exit
created: 2026-06-09T23:06:21-07:00
concluded: 2026-06-10T21:58:16-07:00
pr: https://github.com/gitronald/WebSearcher/pull/170
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

## Log

- 2026-06-10T21:39:33-07:00 — Implemented on `feature/v0.10.0-captcha-exit` (draft PR recorded
  in frontmatter). All four plan steps landed:
  1. `utils.is_sorry_redirect` + module regex (`WebSearcher/utils.py`).
  2. `parse_serp(serp, url=None)` threads the response URL into
     `FeatureExtractor.extract_features(..., url=...)`; `features["captcha"]` is now
     `has_captcha OR is_sorry_redirect`; `SearchEngine.parse_serp` passes `self.serp["url"]`.
  3. All three browser backends capture the live URL + rendered HTML in the `send_request`
     except path; patchright/playwright additionally record the goto status (e.g. 429) before
     the `#search` wait so a timeout keeps the real code. The `searches` loop guard is
     unchanged — the URL signal now feeds it.
  4. Fixture `tests/fixtures/sorry_index.html`: a real `/sorry/index` page captured headless
     via the Evidence repro (plain playwright, blocked on first query, 429), then scrubbed —
     client IP replaced with a TEST-NET-3 placeholder, per-session reCAPTCHA tokens and
     widget ids replaced with `REDACTED` markers. Tests cover `is_sorry_redirect` true/false
     anchoring, `has_captcha` on the fixture, the `extract_features` url path (empty HTML +
     redirect URL -> captcha), end-to-end `parse_serp("", url=sorry)` -> `captcha: True`, and
     no false positives across the fixture corpus URLs.
  - Verified `parse_serp("")` does not raise (empty-HTML block case), so
    `SearchEngine.parse_serp` can't strand stale features on a blocked request.
  - Full suite 525 passed; 87 snapshots unchanged (normal-SERP output byte-identical).

- 2026-06-10T21:58:16-07:00 — Review follow-up (7-angle review posted to the PR; fixes in
  one commit). Actioned, each with regression tests where applicable:
  1. `requests` backend now records the final post-redirect URL (it had discarded
     `response.url`, so the URL signal could never fire for `method="requests"`).
  2. Pre-navigation failures no longer record the *previous* query's SERP under the new
     query: each browser backend snapshots the URL before navigating and the except-path
     capture only runs when the live URL moved off it (new `tests/test_search_methods.py`,
     fake-driver tests for all three backends; zendriver also switched to the local
     `tab.url` property instead of a CDP `evaluate` round-trip).
  3. `is_sorry_redirect` broadened from a `(www.)google.com`-only regex to
     `urlsplit` + `tldextract` (registered domain == `google`, path `/sorry`(`/`)) —
     covers ccTLDs, `ipv4.google.com`, and the no-trailing-slash variant, still rejects
     `google.example.com/sorry/`.
  4. `SearchEngine.parse_serp` resets `self.parsed` before parsing, so a swallowed parse
     error can't leave the previous query's `captcha` flag attributed to the current one.
  5. `ws-demo show` reparses with the stored record URL, keeping collection-time and
     reparse features consistent for blocked captures.
  6. Test hygiene: the fixture test no longer passes `url=` (the HTML path must trip on
     its own); `load_all_serps` is cached to avoid a third full corpus decompress.
  - Conscious no-ops (rationale in the PR review comment): patchright's real-status-
    before-wait, per-backend capture duplication, inline `SORRY_URL` test literals,
    Optional-narrowing guards, and url-less reparse in `bench`/`demos/parse`.
  - Gate after fixes: 537 passed (87 snapshots unchanged), ruff clean, pyrefly 0 errors.

## Retrospective

- The plan's four steps held up unchanged; all the real discovery happened in review. The
  biggest find was not the detection logic but a capture hazard the new except-path code
  introduced: without a pre-navigation URL snapshot, a failure *before* navigating would
  have silently recorded the previous query's SERP under the new query — worse than the
  empty response it replaced. Failure-path captures need a "did we actually move?" guard.
- The plan scoped URL capture to the browser backends and missed that the `requests`
  backend had the same gap with a one-line fix (`response.url`). When a plan says "each X
  backend," check the non-X backends for the same invariant.
- Threading a new signal through `parse_serp` is opt-in per call site; sweeping in-repo
  callers (demo reparse paths) at the same time avoids collection-vs-reparse divergence.
- Capturing the fixture live via the plan's Evidence repro worked on the first try (plain
  playwright headless is reliably blocked), but the raw page contained the client IP and
  session tokens — public-repo fixtures from live captures always need a scrub pass.
- Fake-driver unit tests (bypass `__init__`, stub the page/tab/driver surface) covered
  all three backends' failure paths in <1s with no browser; worth reusing for future
  backend behavior changes.
