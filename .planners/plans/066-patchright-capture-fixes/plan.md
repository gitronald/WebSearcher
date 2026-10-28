---
id: 66
slug: patchright-capture-fixes
status: active
branch: feature/patchright-capture-fixes
created: 2026-10-28T09:27:24-07:00
concluded:
pr:
---

# Make patchright captures settle, isolate requests, and detect challenges by markup

## Context

Long batch runs through the patchright backend (thousands of queries, several engines in
parallel, each under Xvfb) show four problems in `PatchrightSearcher` and the `captcha`
feature. None of them blocks a run. A caller can work around each one by retrying, but the
backend should get them right itself.

1. **The SERP navigates again after `#search` renders.** `send_request` sleeps a fixed 2 s
   after `#search` appears and then calls `page.content()`. On a few percent of requests the
   page replaces itself inside that window. The capture then either raises `Page.content:
   Unable to retrieve content because the page is navigating and changing the content`, or
   returns an early document without error: the SERP shell, about 80 KB, with no
   `id="search"` (it parses as `main_layout=no-rso` with 0 results). This happens on a fresh
   browser with nothing loaded before the query, so it is the page's own behavior. For a few
   query and location pairs it happens on every attempt, so a retry on a fresh engine does
   not help. Only a capture that waits for the second navigation to finish can get the page.
   The "Please click here if you are not redirected" line in that shell is the `<noscript>`
   fallback every full SERP carries, not an interstitial.

2. **One engine reused across queries lets the previous page reach the next request.**
   `send_request` calls `page.goto` on the page that still holds the previous SERP. The
   reload from item 1 can land after the previous request has returned. Three shapes were
   seen: `goto` raising "interrupted by another navigation" to the previous query's URL, an
   early document recorded as a success, and the previous query's complete SERP recorded
   under the new query's URL and metadata. The last one is silent corruption. Clearing
   cookies after each request (`clear_cookies`) may be what prompts the page script to
   reload; this is not confirmed. Until it is fixed, a caller has to build a new engine
   for every query, paying a Chrome launch each time.

3. **The `captcha` feature is a word search.** `utils.has_captcha` returns true when
   "CAPTCHA" appears in the document text. A normal SERP whose result snippet quotes a
   site's form text (for example "CAPTCHA: enabled to secure this form") is flagged on every
   attempt. A caller that pauses on the flag then stalls on a page that is not a challenge.
   The reverse case was seen in a manual session: a challenge shown as an in-page "Captcha
   Dialog" overlay on a normal `/search?q=` SERP with results present. That case is
   detected only if the overlay's text happens to contain the word.

4. **`ai_expand` is silent when the click misses.** `expand_ai_overview` clicks the show-more
   control with a 1 s timeout and returns `None` on failure without logging, then sleeps a
   fixed 2 s after a hit. On a fast workstation the click landed on some runs and missed on
   others for the same query. A caller cannot tell "no overview" from "click missed".

## Plan

### 1. Wait for the page to settle before capturing (`send_request`)

- Replace the second `time.sleep(2)` with a settle step:
  `page.wait_for_load_state("load")` and then `"networkidle"`, each under a short bounded
  timeout. Then confirm `#search` is still attached (`wait_for_selector("#search",
  state="attached")`) before calling `content()`.
- Wrap `content()` in a short retry, about 3 attempts with backoff, that catches only the
  "page is navigating" error. On each retry it waits for the load state again and re-checks
  `#search`.
- After capture, if the HTML has no `id="search"`, log it as a `capture` warning and let the
  response carry a flag for it, so a caller can retry without re-parsing to find out. Decide
  during implementation whether that flag is a new `ResponseOutput` field or a feature in
  the extractor. A new field is preferred: the searcher knows it at fetch time.
- Keep the first `sleep(2)` (before the `#search` wait) unless the settle step makes it
  unnecessary. Measure the request time before and after; the change should not add more
  than about a second at the median.

### 2. Isolate each request from the previous page

- Before `goto`, move the page to a clean state: navigate to `about:blank` and wait for it.
  Or close the page and open a new one in the same context, if that proves more reliable.
  Pick one from a test that reproduces the late-navigation case with a fake page; the
  `about:blank` route is the default.
- Record `pre_nav_url` after the reset, so the exception path's "URL moved" check compares
  against the blank page and never stores the previous query's SERP.
- Investigate whether `clear_cookies` after a request prompts the reload. Run a batch of
  queries on one engine with `clear_cookies=False` and compare the late-navigation rate. If
  it does, move the cookie clear to before the next request's `goto`, after the blank-page
  reset, so no live SERP is on the page when cookies disappear.
- Goal: one engine can serve many sequential queries with no capture carrying another
  query's content. Verify with a run of a few hundred queries on one engine, checking that
  each saved SERP's `<title>` matches its own query.

### 3. Detect challenges from the challenge markup (`utils.has_captcha`)

- Key the feature on challenge markup instead of the word in the visible text:
  - the `/sorry/` page's form (`form#captcha-form`, or an action under `/sorry/`)
  - a reCAPTCHA container (`div.g-recaptcha`, `#recaptcha`, an `iframe` from
    `/recaptcha/`)
  - the in-page dialog overlay
- Build the overlay selector from a saved fixture. If none exists yet, save one the next
  time the overlay appears, and leave this part of the plan open until then.
- Keep `is_sorry_redirect(url)` as an independent signal (plan 048).
- Tests:
  - the existing `/sorry/` fixture still flags
  - a normal SERP with "CAPTCHA" inside a result snippet does not flag
  - a synthetic page with a reCAPTCHA container flags
  - an overlay fixture flags, once one exists
- Note the changed meaning in the CHANGELOG, since callers branch on the flag.

### 4. Make `ai_expand` observable

- Raise the show-more click timeout from 1 s to about 5 s.
- After the click, wait for the control's `aria-expanded="true"` instead of sleeping a fixed
  2 s.
- Log a miss at debug level with `event="ai_expand"` and an outcome (`expanded`, `no_control`,
  `click_failed`). A caller can then tell "no overview" from "click missed".

### Order

`1 -> 2 -> 3 -> 4`. Item 2's verification depends on item 1: a run on one engine is only
clean once a settled capture holds. Items 3 and 4 are independent and can land in either
order.

## Out of scope

- Proxies, IP reputation, and rate limits. These decide whether Google serves a challenge.
  This plan only decides how the backend captures and labels what it gets.
- The requests backend. Its enable-JavaScript redirect (`/httpservice/retry/enablejs`,
  200, `no-rso`) is a separate signal and can be its own plan if a caller needs it labeled.
- Chrome memory per engine and how many engines a host can run in parallel.

## Log

- **2026-10-28T09:39:09-07:00** — Activated.
  - Branch: `feature/patchright-capture-fixes`
  - Base: `dev` at `2133286`
  - Worktree: `.worktrees/066-patchright-capture-fixes`
  - PR: pending
