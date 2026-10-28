---
id: 66
slug: patchright-capture-fixes
status: done
branch: feature/patchright-capture-fixes
created: 2026-10-28T09:27:24-07:00
concluded: 2026-10-28T11:49:55-07:00
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
- **2026-10-28T10:34:35-07:00** — AI expand comparison (user's run, 6 queries on the warmed profile, `data/plan-066/ai-expand-2.jsonl`, with captures from just before and after each click in `ai-expand-2-html/`). All rows have `has_search: true` and matching titles.
    - Outcomes: `expanded` on the 3 queries with an AI overview (sky blue, boil an egg, list comprehension), and `no_control` on the 3 without one. No click missed.
    - The parsed AI overview rows are identical before and after the click on all 3 (same text, sections, citations, and sources).
    - The raw documents have the same text: 0 lines of body text change. The click changes only presentation markup: `data-trnct` goes from true to false, the 383px `max-height` is removed, `aria-hidden` comes off the collapsed part, and a few empty wrapper divs are added. The expanded HTML is 239-1129 bytes smaller. In the current layout the full overview is in the DOM before the click, and expanding only reveals it.
    - Scope: 3 queries, one layout, one session. Older layouts (e.g. 2024 SGE) may have loaded content on expand; not tested.
- **2026-10-28T10:43:25-07:00** — AI overview load timeline (user's run of `probe_ai_timeline.py`, 3 queries, warmed profile, `data/plan-066/timeline.jsonl`). Times are from the start of `goto` unless marked as from `#search`.
    - "why is the sky blue": `#search` 0.98 s, load 1.72 s, network idle 3.18 s. The overview is complete at +0.5 s after `#search` (sources 3 to 8 between +0 and +0.5 s).
    - "how to boil an egg": `#search` 0.94 s, load 2.10 s, idle 2.80 s. Complete at +0.5 s after `#search`.
    - "python list comprehension" (a streamed overview, `data-aim="1"`): `#search` 0.59 s, load 1.15 s, idle 5.14 s. It parses as `unavailable` from +0 to +1.5 s, has text at +2 s, sections grow from 1 to 3 by +4 s, and sources go from 0 to 3 to 7 by +5 s. It is stable from +5.0 s after `#search` (5.6 s from `goto`). One request stays in flight from +0.5 to +4 s, so network idle (5.14 s) marks the end of the stream.
    - What this means for the settle step: network idle tracks the overview's end, but the 3 s cap (`NETWORKIDLE_TIMEOUT_MS`) only covers the streamed case because the first `sleep(2)` delays the idle wait's start to about 2.5 s from `goto` (cap ends about 5.5 s, idle came at 5.14 s). Dropping that sleep without raising the cap would capture the streamed overview part-way through. The cap costs time only on a page that never goes idle, and all 3 went idle.
    - The streamed overview's early captures reproduce the requests-backend mislabel in a browser: a not-yet-loaded overview parses as `unavailable` (plan 067).
- **2026-10-28T11:03:57-07:00** — AI overview load timeline, second run (user's run, 18 queries, warmed profile, `data/plan-066/timeline-2.jsonl`). Times are from `#search` unless marked.
    - 11 overviews were stable by +0.5 to +1.0 s. 3 streamed (python list comprehension, chargers vs raiders, astronomical clocks czech republic) and were stable at +5.0, +3.0, and +3.0 s. 1 query had no AI overview (suwanee-painters).
    - The network-quiet wait never fired early. On every query the first 500 ms quiet stretch came after load. On the 3 streams it began as the stream ended (+4.42, +2.78, +2.99 s), between the last capture that changed and the first stable one.
    - 4 of 18 pages never went quiet in 12 s (stripped screw, learn spanish, cook a turkey, fruit flies), though their overviews were stable by +0.5 s. On those, the network-idle wait always runs to its cap, so the cap is a cost on about a fifth of searches. That rules out a large cap like 8 s.
    - The "Generating" spinner is not a completion signal. On the 3 streams it went from 1 to 0 at +1.5 to +2.0 s, when text began to arrive, 1-3 s before the stream ended. `div.mZJni` (the body) appears at +0.5 to +1.0 s, also early. Neither marks the end. Only the network going quiet does.
    - With the 3 s cap, starting about 2 s from `goto` (after the first sleep), the settle step covers `networkidle` firing up to about 5.1 s from `goto`. Chargers (about 4.1 s) and astronomical clocks (about 4.1 s) fit. Python list comprehension (5.62 s) does not, so its capture comes at the cap, between +4 and +5 s after `#search`, around the stream's end.
- **2026-10-28T11:25:44-07:00** — Run 5 (user's run, 7 queries, `data/plan-066/timeline-3.jsonl`) and the settle-step fix.
    - What keeps a page busy: on all 4 never-quiet pages, one `www.google.com/goto` request (type `other`) starts at 0.4-0.9 s from `goto` and is still open at the end. Every SERP carries a `<script type="speculationrules">` that prefetches its top results' `/goto?url=` links. The recurring requests (`gen_204` pings, `play.google.com/log`) all finish.
    - The stream: on the 3 streamed pages, one `www.google.com/async/folsrch` fetch is open from about 0.3 s to 3.0-3.8 s from `goto`, and the quiet stretch begins as it ends.
    - Local check (headless Chrome against a page on 127.0.0.1 whose speculation rules prefetch a URL that does not answer; scripts in the session scratch, not kept): Chrome sends `Sec-Purpose: prefetch` on the prefetch and the driver shows it in `request.headers` at the request event, with resource type `other`. The driver's `networkidle` counts the prefetch: with a 20 s hold it fired at 10.5 s (Chrome drops the prefetch after about 10 s), against 20.6 s for a plain `fetch()`.
    - Fix: `NetworkTracker` in `patchright_searcher.py` tracks the page's requests in flight, ignoring `Sec-Purpose: prefetch`, and `settle_page` waits for 500 ms with none in flight, in place of the driver's `networkidle`. It is attached after the blank-page reset and before the search's `goto`, and detached in `send_request`'s `finally`. `NETWORKIDLE_TIMEOUT_MS` goes from 3 s to 8 s, about twice the latest stream end measured from the settle step's start (about 3.6 s). With prefetches ignored, the cap should only bite on pages that are still busy.
    - Tests: fake-page tests for the tracker (prefetch ignored, busy until the request ends, cap, detach) and for the settle step waiting on a request in flight. `tests/test_patchright_network.py` runs the tracker in headless Chrome against a local server: a hanging prefetch is ignored (quiet within 2 s, and the prefetch request is asserted to have been made), and a plain request held 1.5 s is waited for. The full suite passes (905).
    - Not verified on Google: that the `/goto` requests carry `Sec-Purpose: prefetch`, and the new timing. Handoff run 6.
- **2026-10-28T11:34:41-07:00** — Run 6 (user's run, the same 7 queries, warmed profile, `data/plan-066/timeline-4.jsonl` and `settle.jsonl`).
    - Prefetch marker confirmed on Google: on all 4 formerly never-quiet pages the open `www.google.com/goto` request (type `other`) carries `Sec-Purpose: prefetch`. The 3 `async/folsrch` streams carry none and end at 3.2-4.15 s from `goto`.
    - Settle step, end to end (`send_request` on this branch): the 4 formerly never-quiet queries took 3.12-3.29 s, and the 3 streamed ones 4.24-4.74 s. All 7 have `#search` and a title matching their query. Every request finished well under the cap (the 2 s sleep plus an 8 s cap would put a capped request near 10 s), so none ran to the cap. This is inferred from timing; the DEBUG console output was not saved. Under the previous settle step the 4 would have run to the 3 s cap, about 5 s in all; that is inferred, not measured on these queries.
    - Streamed overviews captured complete, as far as separate page loads can show: python list comprehension 4 sections and 7 sources (timeline final 4 and 7), chargers vs raiders 2 and 5 (timeline 2 and 3), astronomical clocks 2 and 5 (timeline 2 and 6). Each capture came after its own stream would have ended. Overview content varies between loads (an instant overview, "best way to learn spanish", had 1 section and 6 sources here, 4 and 15 in the timeline load), so the counts cannot be compared exactly.
- **2026-10-28T11:38:13-07:00** — Dropped the first `sleep(2)` (before the `#search` wait), so the settle step is the only wait. Live run by the session, with the user's go-ahead: the same 7 queries, one engine, warmed profile, `data/plan-066/settle-nosleep.jsonl`.
    - All 7 have `#search` and matching titles. No WARNING or ERROR lines and no "network busy at cap" lines on the console.
    - No time saved. Without the sleep: 2.61-3.82 s for the 4 instant overviews and 4.64-5.63 s for the 3 streams, median 3.82 s. With it (run 6): 3.12-3.29 s and 4.24-4.74 s, median 3.29 s. Per-query differences run from -0.5 to +1.0 s, which 7 queries cannot separate from load-to-load variation. After `#search` the page keeps loading scripts and sending pings until about 2.5-3 s from `goto` (timeline runs), so the quiet wait now covers the time the sleep used to.
    - No loss in completeness. The instant overviews parse to the same sections, sources, and text as run 6. The streams have as many or more sources (list comprehension 7 and 7, chargers 5 and 7, astronomical clocks 5 and 7).
    - Kept: the settle step adapts to each page, where the sleep was a fixed delay overlapping it.
- **2026-10-28T11:50:19-07:00** — Review gate: /code-review at medium on PR #213 (correctness and reuse finders, then verifiers), posted to the PR. Checks pass (906 tests, ruff, ruff format, pyrefly) and CI is green on 3.12-3.14.
  - Review follow-up: raised `expand_ai_overview` calling `show_more.count()` outside its try, so a closed page escaped to `send_request` as an ERROR fetch failure. Actioned in `1b04c79`: the count moved inside the try and logs `click_failed`, with a regression case in `test_expand_ai_overview_outcomes`.
  - Rejected after verification: `reset_page` closing the only page (a probe showed the persistent context survives, headless and headed), and `has_search` missing an unquoted `id=search` (all 121 fixture SERPs agree with a parsed `#search`).
  - Conscious no-ops: the second `#search` check after settling and the backoff before re-settling are intended by the plan; the probe scripts' duplicated helpers and the overlapping captcha tests at the utils and extractor levels are left as they are.

## Handoff

### State

- Closed. Items 1-4 are implemented on `feature/patchright-capture-fixes` (PR #213),
  reviewed, and merged into `dev` with this close. The review's one finding was fixed
  (Log). `uv run pytest` (906), `ruff check`, `ruff format --check`, and `pyrefly check`
  pass, and CI is green.
- Item 1 went further than the spec, from the live runs (Log): both fixed 2 s sleeps are
  gone. The settle step waits for load, then for 500 ms with no request in flight, ignoring
  speculative prefetches (`Sec-Purpose: prefetch`), capped at 8 s. The driver's
  `networkidle` is no longer used, because a SERP's prefetch of a result link held it to
  its timeout.
- Live checks, all run on 2026-10-28 on one warmed profile (`data/plan-066/`, ignored):
  dev against branch timing and isolation, the `ai_expand` comparison, three AI overview
  load timelines, the prefetch check, and the settle step with and without the first sleep.
  The results are in the Log. They used `clear_cookies=False`, so the cookie clear after
  each request was not exercised.
- Sidecar probes, for repeating any of these: `probe_one_engine.py` (per-query timing,
  isolation, AI overview counts, and before/after-click captures with `--ai-expand`) and
  `probe_ai_timeline.py` (captures at fixed offsets after `#search`, with network
  timings and request URLs). Usage is in each script's docstring. Both need a warmed
  profile (`--user-data-dir`); a fresh profile was challenged on its first query.

### Remaining

1. Nothing in this plan. The open questions below are settled or left open on the record,
   and none blocks the merge.
2. Plan 067 (not-loaded AI overviews labelled `unavailable`) is a separate draft.

### Open questions

1. **Settled, not pursued (2026-10-28).** Does clearing cookies after a request prompt the late reload? Not investigated: it needs
   a few hundred queries per arm, with `clear_cookies` on and off. Left open by decision
   (2026-10-28). The cookie clear stays after the request. The blank-page reset before the
   next `goto` already keeps a late reload out of the next request.
2. **Settled, not pursued (2026-10-28).** The plan's isolation run (a few hundred queries on one engine, each `<title>` matching
   its query) is not run, for the same reason. The probe script does this check when given
   a longer query list.
3. **Left open, not verified.** No follow-up plan owns it; a non-English overlay capture would answer it. Is the `Captcha Dialog` aria-label localized? The overlay selector also matches the
   dialog's `/sorry/` iframe, which does not depend on language, so a non-English overlay
   should still flag. Not verified.
4. **Out of scope, the user's decision.** No follow-up plan yet. Should `ai_expand` stay? In the current layout the click added no data on 3 of 3
   queries (see Log), while the click and wait add time to each query that has an
   overview. The decision is out of this plan's scope and is the user's to make.

## Retrospective

- The plan's settle step (load, then the driver's `networkidle`) was not enough. Live
  timelines showed the SERP's speculative prefetches of result links held `networkidle`
  to its cap on about a fifth of pages. A tracker that ignores `Sec-Purpose: prefetch`
  replaced it, and both fixed sleeps went away with no loss in completeness.
- Measuring before deciding paid off. The `ai_expand` before/after comparison showed the
  click adds no data in the current layout, and the load timelines located streamed
  overviews' end, which set the 8 s cap from evidence instead of a guess.
- Live checks ran by hand on a warmed profile, since a fresh profile was challenged on its
  first query. The sidecar probes made each run repeatable; keep that pattern for
  backend changes.
- Two of the plan's verification goals (the cookie-clear question and a few-hundred-query
  isolation run) were set aside because their cost was too high for what they would
  settle; the blank-page reset covers the risk they were meant to measure.
- The review's one finding (an unguarded `count()` in `expand_ai_overview`) came from
  restructuring a function whose old version swallowed every error. When narrowing a
  broad `except`, check every call that moved out of it.
