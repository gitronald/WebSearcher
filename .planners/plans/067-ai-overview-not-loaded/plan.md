---
id: 67
slug: ai-overview-not-loaded
status: active
branch: feature/ai-overview-not-loaded
created: 2026-10-28T10:44:00-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/216
---

# Tell a not-loaded AI overview from a declined one

## Context

`parse_ai_overview` sets `sub_type: "unavailable"` when an AI overview component yields
no text and no details, and its text contains one of `_UNAVAILABLE_MARKERS` ("An AI
Overview is not available for this search", "Can't generate an AI overview right now").
The label is meant to record that Google declined to write an overview. But both messages
are shipped on every AI overview page, so the rule cannot tell a decline from an overview
whose body has not loaded yet. Most `unavailable` rows are probably the second case.

Evidence (gathered during plan 066):

- **Requests captures.** Of the 14 AI overview rows in the fixture corpus captured with
  the requests backend, 9 parse as `unavailable`, and 3 of the other 5 have no sources.
  The overview body and sources are filled in by the page's JavaScript after the first
  HTML, which the requests backend never runs. Every browser-captured row (selenium,
  patchright) has a body and sources.
- **Browser timeline.** On patchright, a streamed overview ("python list comprehension",
  `data-aim="1"`) parses as `unavailable` for the first 1.5 s after `#search`, then fills
  in: text at +2 s, all sections by +4 s, all sources by +5 s (plan 066 Log, the AI
  overview load timeline entry).
- **Markup.** Every `unavailable` row in the corpus, from either backend, and the browser
  capture taken before the overview loaded look the same: no body container
  (`div.mZJni`), and both messages present inside a `span.YWpX0d` with an inline
  `display:none`. Loaded overviews (body present) carry the same two hidden messages, or
  none.
- **No confirmed decline.** No capture in hand shows either message visible. A real
  decline is presumably shown by JavaScript removing the `display:none` from one message,
  but that is not verified.

Repro (fixture corpus; add capture paths as arguments):

```bash
uv run python .planners/plans/067-ai-overview-not-loaded/ai_overview_states.py
```

It prints, per AI overview row, the parsed `sub_type`, whether `div.mZJni` is present,
and what hides each decline message.

## Plan

### 1. Capture a real decline

- On the patchright backend with a warmed profile, search queries that are likely to be
  declined. Candidates: the corpus's requests-backend `unavailable` queries ("chargers vs
  raiders", "astronomical clocks czech republic", "suwanee-painters"). Let each capture
  settle past the stream end (plan 066 measured up to 5 s after `#search`).
- For each one that shows a message instead of an overview, save the capture and record
  how the message is shown: which message, and whether the `display:none` is gone or
  something else changes.
- Save one trimmed decline fixture under `tests/fixtures/`, and one not-loaded fixture
  trimmed from an early browser capture (the plan 066 timeline probe's
  `probe_ai_timeline.py` saves one as `<slug>.first.html`).
- If no query declines after a reasonable search, record that, and go to step 2 with the
  decline rule left out.

### 2. Split the label

- Add a `sub_type` for an overview whose body has not loaded. Pick the name during
  implementation (`not_loaded` is the working name), and check it against the existing
  `ai_overview` sub-types so the vocabulary stays small.
- `unavailable` only when a decline message is shown (not under `display:none`), per the
  markup found in step 1.
- `not_loaded` when there is no body, no text, no details, and both messages are hidden.
- A requests-backend capture can never show a decline (the decline is shown by
  JavaScript), so its empty overviews become `not_loaded`.

### 3. Tests and docs

- Fixture tests for both states, plus the existing `unavailable` tests re-pointed to the
  rule that applies.
- Snapshot updates for the corpus rows that flip (the requests-backend and 2025
  `unavailable` rows listed by the repro script). Confirm that each flip is only the
  `sub_type`.
- CHANGELOG "Changed" entry: a row-label change. Callers that count `unavailable` as
  declines will see most of those rows move to the new label.

### Order

`1 -> 2 -> 3`. Step 2's decline rule depends on what step 1 finds. The `not_loaded` rule
does not, so it can land first if step 1 stalls.

## Out of scope

- Making the requests backend load the overview. It cannot run the page's JavaScript.
- How long the browser backend waits for the overview to finish (plan 066, item 1).

## Log

- **2026-10-28T11:03:57-07:00** — Decline candidates captured in a browser (plan 066's second timeline run, patchright, warmed profile, `data/plan-066/timeline-2.jsonl`, captures in `timeline-2-html/`).
    - "chargers vs raiders" and "astronomical clocks czech republic" each loaded a full overview (sectioned, 4 sources) by +3 s after `#search`. Their requests-backend `unavailable` rows in the corpus were overviews that had not loaded, not declines.
    - "suwanee-painters" had no AI overview component at all in the browser, while the requests capture (two days earlier) had one with no body. Not a decline capture either.
    - Still no capture with a decline message shown. Step 1 stays open.
- **2026-10-28T12:44:36-07:00** — Activated.
  - Branch: `feature/ai-overview-not-loaded`
  - Base: `dev` at `b7eebfe`
  - Worktree: `.worktrees/067-ai-overview-not-loaded`
  - PR: pending
- **2026-10-28T12:53:31-07:00** — PR opened: https://github.com/gitronald/WebSearcher/pull/216
