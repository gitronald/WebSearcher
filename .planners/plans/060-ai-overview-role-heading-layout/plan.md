---
id: 60
slug: ai-overview-role-heading-layout
status: active
branch: feature/ai-overview-role-heading-layout
created: 2026-10-15T11:24:54-07:00
concluded:
pr:
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
