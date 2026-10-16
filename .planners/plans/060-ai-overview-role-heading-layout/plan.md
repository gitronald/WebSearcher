---
id: 60
slug: ai-overview-role-heading-layout
status: done
branch: feature/ai-overview-role-heading-layout
created: 2026-10-15T11:24:54-07:00
concluded: 2026-10-16T15:05:56-07:00
pr: https://github.com/gitronald/WebSearcher/pull/203
---

# Recognize the reworked AI overview layout

## Plan

**Problem.** AI overviews collected on 2026-10-15 come in a layout the parser
does not recognize, so none of them is parsed with content. The "AI Overview"
heading is now a `div[role="heading"]`, not an `h2`, and there is no
`div.Fzsovc`. Inside the overview, the body and source markers
`parse_ai_overview` reads (`div.rPeykc`, `button.rBl3me` citations,
`ul.bTFeG` / `li.CyMdWb` source tray) are gone. What remains: the `EYwa3d`
controller, `div.hdzaWe`, the `div.mZJni` content container, nested
`[role="heading"]` section headings, and `[data-src-id]` source ids.

Two failures follow:

- **Classification.** `ClassifyMain.ai_overview` gates on `Fzsovc` or an `h2`,
  so it never fires. `knowledge_panel`, earlier in the chain, claims most of
  these components as `knowledge`. The rest fall through to the end-of-chain
  `ai_overview_banner` rule (keyed on `EYwa3d`) and are typed `ai_overview`.
- **Parsing.** Those that reach `ai_overview` come out as `sub_type="flat"`
  with empty text and no details, since none of the body markers match.

The fixture corpus has no SERP in this layout, which is why the snapshot
suite stayed green.

**Evidence** (counted with the sidecar `probe_aio_layout.py`, at the component
level, through the real extractor and classifier):

| Source | SERPs with the overview controller | Layout | Typed as |
|---|---|---|---|
| 2026-10-15 batch run, `data/demo-ws-v0.11.7a2-warm-profile/serps.json` (45 SERPs) | 27 | all new | 17 `knowledge`, 10 `ai_overview` (all 10 empty: no text, no details) |
| Fixture corpus, `tests/fixtures/serps.json.bz2` (102 SERPs) | 30 | 21 old, 6 old+new, 3 with no heading | 28 `ai_overview`, 2 `knowledge` |

The run's file is local collection output (`data/` is git-ignored), so step 1
moves the SERPs this plan needs into the committed corpus. Lines (0-indexed)
0, 3, and 4 ("why is the sky blue", "best credit cards", "car insurance
quotes") are typed `knowledge`; line 5 ("cheap flights to new york") is the
empty `ai_overview`.

```bash
P=.planners/plans/060-ai-overview-role-heading-layout/probe_aio_layout.py
uv run python $P data/demo-ws-v0.11.7a2-warm-profile/serps.json            # per-SERP detail
uv run python $P data/demo-ws-v0.11.7a2-warm-profile/serps.json --summary  # counts only
uv run python $P tests/fixtures/serps.json.bz2 --summary
```

**Steps.**

1. **Fixtures.** Add new-layout SERPs from the run to
   `tests/fixtures/serps.json.bz2`: at least one that is typed `knowledge` today
   and the one typed as an empty `ai_overview`, picking queries whose overviews
   differ in shape (lists, section headings, source count). Add coverage tests
   in `tests/test_parser_coverage.py` that fail on current code.
2. **Classify.** Find which `_KNOWLEDGE_PANEL_CSS` selector matches inside the
   overview. Then add a structural signal for the new layout ahead of
   `knowledge_panel`, such as the `EYwa3d` controller together with
   `div.mZJni`, rather than the English heading text. No component in the
   existing corpus may change type: the snapshot suite must stay byte-identical
   outside the new fixtures.
3. **Parse.** Extract the body text, section headings, inline links, and sources
   (via `[data-src-id]`) from the new markup, alongside the current and legacy
   paths. Reuse the existing `details.type` labels and drop empty payloads
   instead of emitting null-filled dicts.
4. **Snapshots and review.** Regenerate snapshots for the new fixtures only. The
   PR shows before and after parsed rows for each new fixture.

**Open questions.**

1. Is the new layout replacing the old one, or are both served (by session,
   query, or experiment)? Keep both parse paths either way. The corpus has 6
   SERPs carrying both markers.
2. In the run, `people_also_ask` components also contain overview markup
   (answers that embed an AI overview). Should those be parsed, or left as part
   of the question block? Not in scope until answered.
3. The 3 corpus SERPs with the controller and no heading may be the existing
   "unavailable" banner case. Confirm during step 2 that the new rule does not
   change how they are typed.

## Log

- **2026-10-16T10:33:11-07:00** — Activated.
  - Branch: `feature/ai-overview-role-heading-layout`
  - Base: `dev` at `3b4283e`
  - Worktree: `.worktrees/ai-overview-role-heading-layout`
  - PR: pending
- **2026-10-16T10:50:37-07:00** — PR opened: https://github.com/gitronald/WebSearcher/pull/203
- **2026-10-16T10:50:57-07:00** — Implemented steps 1-4; corpus check: all 27 overviews in the 2026-10-15 run now type `ai_overview` with text (all `sectioned`), and no existing corpus component changes type.
  - Fixtures: three new-layout SERPs, not four. "cheap flights to new york" was dropped: its flights widget now parses as a hollow `general` row and fails `test_general_results_have_title_or_url`, a separate gap. "is it worth learning rust reddit" covers the empty-`ai_overview` case instead. The sidecar `add_fixtures.py` appends them, keyed by `serp_id`; three of the queries repeat older corpus records, so the tests key on `serp_id` too.
  - Classify: `ai_overview` also claims `EYwa3d` + `div.mZJni`, ahead of `knowledge_panel`. The `knowledge` match was `div[jscontroller="qTdDb"]` inside the overview. People-also-ask answers carry `mZJni` but never the controller (31 in the run), so they are not claimed.
  - Payloads were part of the cause: the new layout writes `<!--TgQPHd|||...-->` (three pipes) and the regex took one, so no citation payload was read. Type-A entries now carry a `/goto?url=` redirect, and a new header shape `[uuid, null, null, 0, favicon, publisher, total, full_url]` names the full URL of each button's lead source.
  - Parse: the plan's marker list was wrong about `mZJni` scope. The container stays, so the current-DOM path is extended, not a third path: paragraphs `div.n6owBd`, headings `div[role=heading][aria-level=3]`, lists `XSq4R`/`T9WCjf`, citations `button.vDOt8c` (wrapper `span.NMq1me` stripped), sources from `div[data-src-id]` cards, in two tray shapes (`cRH23c` below the body, `fSJHKf` inside it). The closing follow-up prompt (`div.AHmQrc`, "Would you like to know ...") is left out of the text.
  - Redirect resolution: a bucket's first Type-A entry takes the header URL when publisher and domain agree, or, failing that, the one redirect across buckets that fits. In the run, 186 of 344 redirects (54%) resolve with no conflicts, and 125 of 212 tray sources (59%). Matching the `[full_url, ..., title, snippet, thumb, publisher]` blobs by title would add about 19 more; not done.
  - Snapshot deviation: fixture `fc9c7b848175` ("american1967", counted "old+new" by the probe) already used the new body markup, so its snapshot changes (gains its lede and two citations). Every other existing snapshot is byte-identical.
  - Found while testing: a comma-union selector returns an element once per selector it matches; old `otQkpb` headings also carry the role attributes, so headings are de-duplicated by `mem_id`.
  - Open question 3 answered: the three controller-without-heading corpus SERPs keep their types (2 `ai_overview` unavailable, 1 `knowledge`).
  - Checks: `uv run pytest` 693 passed; ruff and pyrefly clean. The new coverage and payload tests fail on `dev` (14 of 15; the PAA guard passes on both).
  - Repro: `uv run python .planners/plans/060-ai-overview-role-heading-layout/probe_aio_layout.py data/demo-ws-v0.11.7a2-warm-profile/serps.json --summary` now prints `('new', 'ai_overview'): 27`.
- **2026-10-16T10:52:42-07:00** — Implemented: 6 commits ahead of `dev`.
- **2026-10-16T14:55:13-07:00** — Review gate run (/code-review, medium); fixes in 2c1b847; review posted on PR #203.
  - Review follow-up: 12 candidates from two finders, 7 verified, 4 kept. Actioned: the TgQPHd regex stopped at the first pipe run, so `<!--TgQPHd|<keys>|[[...` comments kept their keys and failed to parse; it now skips to the last pipe before the JSON (`<!--TgQPHd[^\[>]*\|(\[.+?)-->`), with `test_keys_between_pipes_skipped` (fails on the old regex) and `test_comment_without_json_does_not_swallow_next`. Across 150 corpus and run SERPs no payload bucket is lost; the two recovered comments in `fc9c7b848175` match no payload shape, so no parsed output changes. Reworded the stale "Deduplicate" comment on `_drop_nested_descendants`. Conscious no-ops: same-site header-to-redirect mismatch in `_names_source` (all 16 fixture mappings check out; already under Not verified) and an unwrapped `button.vDOt8c` leaking its label (none in the corpus; stripping it inside a decomposed wrapper risks a dangling node). Checks: 695 passed, 105 snapshots unchanged, ruff and pyrefly clean.
- **2026-10-16T15:07:12-07:00** — Handoff questions 4 and 5 done in this PR, question 2 handed to plan 061 (user decisions, 2026-10-16).
  - Q5, flights widget (3d5bab3): the `es75Cc` flight-search widget, headed "Flight prices" in the older corpus capture, is now headed "Search flights", so `ClassifyMain.flights` missed it and it fell through to a hollow `general` row. `flights` now also matches the `es75Cc` controller, which appears in no other component across the 150 corpus and run SERPs. Added fixture `3765fb676f3c` ("cheap flights to new york", via `add_fixtures.py`), which also covers the empty-`ai_overview` case the plan first listed. Its widget parses as `flights` with 4 fare links; `test_flight_search_widget_search_flights_heading`.
  - Q4, follow-up prompt (9493943): the closing `div.AHmQrc` prompt (21 of 27 run overviews) is kept out of the text and reported as `details["follow_up"]`. Snapshot changes: `ef30639b2b33` and `3765fb676f3c` gain the key, nothing else; `test_ai_overview_role_heading_follow_up`.
  - Q2, PAA-embedded overviews: handed to plan 061 (31 of 37 PAA components in the run hold one under their first question).
  - Checks: 701 passed, 106 snapshots, ruff and pyrefly clean.

## Handoff

**State.** Done. Steps 1-4, the review fixes, and the Handoff follow-ups (questions 4 and 5) are committed and pushed on `feature/ai-overview-role-heading-layout` and merge through PR #203. Nothing is uncommitted.

**Questions.**

1. Is the new layout replacing the old one, or are both served? Answered 2026-10-16: settled for this plan. Both parse paths are kept, so no action is needed either way; revisit only if old-layout captures stop appearing.
2. Should overview markup inside `people_also_ask` answers be parsed? Handed to plan 061 (2026-10-16), which decides the hybrid output shape first.
3. Do the 3 controller-without-heading corpus SERPs change type? Answered 2026-10-16: no.
4. Should the closing follow-up prompt (`div.AHmQrc`) be kept? Answered 2026-10-16: yes, as `details["follow_up"]`, kept out of the text (9493943).
5. Should the new flights widget (hollow `general` on "cheap flights to new york") be fixed? Answered 2026-10-16: fixed in this PR; `flights` matches the `es75Cc` controller (3d5bab3).

**Not verified.** The redirect-to-URL matching is checked against the 27 run overviews and the new fixtures only (no conflicts there); the header-is-lead-source reading is inferred from that run. A same-site header could in principle map to the wrong page's redirect (`_names_source` matches by publisher and domain only); not seen.

## Retrospective

- The plan's marker list was half wrong: `div.mZJni` survived, so extending the current-DOM path beat adding a third parse path. Re-grounding markers in the real pipeline before coding (as the probe did) was what caught it.
- Half the cause was in the payload regex, not the DOM: the triple-pipe comment form dropped every citation payload. The review then found the regex still missed keys between pipes. A corpus-wide old/new bucket comparison is a cheap guard for any change to that regex.
- Holding a fixture back because it tripped an unrelated check (the flights row) left a Handoff question that turned out to be a one-line classifier fix. Fix such small neighbors in the same PR when the signal is clear.
- `serp_id`-keyed fixtures were needed because several new queries repeat older corpus records; query-keyed lookups would have silently picked the old capture.
- Observed, not investigated: in the 2026-10-15 run, many organic `general` rows also carry `/goto?url=` redirects as their URL. Worth a look on the next batch run.
