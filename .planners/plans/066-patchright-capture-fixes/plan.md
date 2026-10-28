---
id: 66
slug: patchright-capture-fixes
status: implemented
branch: feature/patchright-capture-fixes
created: 2026-10-28T09:27:24-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/213
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
- **2026-10-28T09:46:37-07:00** — PR opened: https://github.com/gitronald/WebSearcher/pull/213
- **2026-10-28T10:02:41-07:00** — Implemented items 1-4; tests and checks pass, no live searches run (the user runs them by hand).
    - Item 1: the fixed 2 s sleep after `#search` became `settle_page` (load, then networkidle, each bounded, then `#search` attached). `page_content` retries `content()` up to 3 times on the "page is navigating" error only. The flag is a computed `has_search` on `ResponseOutput`, carried into `BaseSERP` and the saved record. A computed field covers both backends from one definition. The first `sleep(2)` is kept until timing is measured.
    - Item 2: `reset_page` navigates to `about:blank` before each `goto`, and replaces the page (`context.new_page()`) when that navigation is interrupted or ends elsewhere, so `pre_nav_url` is always the blank page. The reset is not done after the capture, because `ws-demo --leave-open` keeps the SERP on screen for solving a challenge by hand. The cookie clear stays after the request (decision below).
    - Item 3: `has_captcha` matches `CAPTCHA_SELECTOR` (`form#captcha-form`, a `/sorry/` form action, `div.g-recaptcha`, `#recaptcha`, a `/recaptcha/` or `/sorry/` iframe, and the `Captcha Dialog` dialog). An overlay capture already existed in the main checkout's ignored `data/`. `tests/fixtures/captcha_dialog_overlay.html` is the trimmed dialog from it, with the continue token redacted. None of the selectors matches any of the 121 corpus SERPs. One corpus SERP ("central park new york", snippet "protected by reCAPTCHA") went from `captcha: true` to `false`; it is the only snapshot change.
    - Item 4: the show-more click and the `aria-expanded="true"` wait use 5 s. In the corpus, 9 of 33 show-more controls have no `aria-expanded`, so those clicks keep a 2 s sleep and log `unconfirmed`. Outcomes: `expanded`, `unconfirmed`, `not_expanded`, `no_control`, `click_failed`, `capture_failed`, in the message text, because the JSONL formatter drops unknown `extra=` keys.
- **2026-10-28T10:03:03-07:00** — Implemented: 6 commits ahead of `dev`.
- **2026-10-28T10:31:04-07:00** — Live probe, run by hand by the user on one warmed persistent profile (`clear_cookies=False`), 6 queries per run, outputs in the ignored `data/plan-066/`.
    - Isolation: all 18 rows (dev, branch, and branch with `--ai-expand`) have `has_search: true` and a `<title>` that names their own query.
    - Timing: dev median 5.54 s (4.60-6.31), branch median 3.33 s (2.63-5.59), so the branch is about 2.2 s faster at the median, within the plan's limit. Both runs report version `0.12.4a0`, so the rows cannot show which code ran. The dev/branch split rests on the checkout each run was launched from.
    - AI expand: not answered by this run. The probe kept only summary rows, so the click's effect could not be separated from the differences between page loads (e.g. "central park new york" was 3.7 MB without expansion and 2.6 MB with it, on separate loads). The probe now saves the page just before and after the click on the same load, and compares the parsed AI overview rows.

## Handoff

### State

- Items 1-4 are implemented on `feature/patchright-capture-fixes` (PR #213), committed and
  pushed. `uv run pytest`, `ruff check`, `ruff format --check`, and `pyrefly check` pass.
- `probe_one_engine.py` (sidecar) runs queries in sequence on one engine and appends a
  JSONL row per query: seconds, `has_search`, whether the `<title>` names its own query,
  final URL, and HTML length. It imports whichever WebSearcher the running environment
  has, so the same script times `dev` from the main checkout and this branch from the
  worktree.

### Not verified (live checks, run by hand)

The user runs the live searches by hand. Each run below opens one headed Chrome. Run them
in this order: the main checkout's environment imports `dev`'s code, and the worktree's
imports this branch. A fresh temp profile was challenged on its first query (2026-10-28),
so every run uses one profile, warmed first. With a profile the probe keeps cookies
between requests (`clear_cookies=False`, as `ws-demo` does), so these runs do not exercise
the cookie clear after each request.

0. Warm the profile (from the main checkout). Solve the challenge if one appears, search
   a little by hand, then press Enter to close:

       uv run ws-demo search "why is the sky blue" --user-data-dir .ws_profile --leave-open

1. Baseline on `dev` (from the main checkout):

       uv run python .worktrees/066-patchright-capture-fixes/.planners/plans/066-patchright-capture-fixes/probe_one_engine.py \
         --out data/plan-066/dev.jsonl --user-data-dir .ws_profile \
         "why is the sky blue" "central park new york" "how to boil an egg" \
         "python list comprehension" "weather tomorrow" "best pizza near me"

2. This branch, same queries and profile (from the worktree):

       uv run python .planners/plans/066-patchright-capture-fixes/probe_one_engine.py \
         --out ../../data/plan-066/branch.jsonl --user-data-dir ../../.ws_profile \
         "why is the sky blue" "central park new york" "how to boil an egg" \
         "python list comprehension" "weather tomorrow" "best pizza near me"

   Pass: every row has `has_search: true` and `title_matches: true`, and the branch's
   median `seconds` is no more than about 1 s above the `dev` median. If it is well
   below, the first `sleep(2)` in `send_request` may be dropped as well (plan item 1).

3. AI expand on this branch, same queries (from the worktree); read the
   `SERP | ai_expand | <outcome>` DEBUG lines on the console. Queries without an AI overview
   should log `no_control`:

       uv run python .planners/plans/066-patchright-capture-fixes/probe_one_engine.py \
         --out ../../data/plan-066/ai-expand.jsonl --user-data-dir ../../.ws_profile \
         --ai-expand "why is the sky blue" "central park new york" "how to boil an egg" \
         "python list comprehension" "weather tomorrow" "best pizza near me"

### Open questions

1. Does clearing cookies after a request prompt the late reload? Not investigated: it needs
   a few hundred queries per arm, with `clear_cookies` on and off. Left open by decision
   (2026-10-28). The cookie clear stays after the request. The blank-page reset before the
   next `goto` already keeps a late reload out of the next request.
2. The plan's isolation run (a few hundred queries on one engine, each `<title>` matching
   its query) is not run, for the same reason. The probe script does this check when given
   a longer query list.
3. Is the `Captcha Dialog` aria-label localized? The overlay selector also matches the
   dialog's `/sorry/` iframe, which does not depend on language, so a non-English overlay
   should still flag. Not verified.
