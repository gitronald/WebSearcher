---
id: 61
slug: paa-embedded-ai-overview
status: done
branch: feature/paa-embedded-ai-overview
created: 2026-10-16T15:06:11-07:00
concluded: 2026-10-16T20:21:30-07:00
pr: https://github.com/gitronald/WebSearcher/pull/204
---

# Parse the AI overview answer embedded in people also ask

## Plan

**Problem.** In the 2026-10 layout, most `people_also_ask` components carry a
generated answer under their first question. It is pre-expanded and uses the
same markup as the role-heading AI overview (plan 060): a `div.mZJni` body with
`n6owBd` paragraphs, `[role=heading][aria-level=3]` section headings,
`button.vDOt8c` citation buttons, and `div[data-src-id]` source cards. The PAA
parser keeps only the question list (`details.type: "text"`), so the answer, its
citations, and its sources are lost. The answer differs from the page's main
overview; it is not a copy.

Plan 060 left these alone on purpose. Its `ai_overview` rule needs the `EYwa3d`
controller, which PAA answers lack, so they stay typed `people_also_ask`
(Handoff question 2 there).

**Evidence** (sidecar `probe_paa_aio.py`, component level, through the real
extractor and classifier):

| Source | PAA components | With an embedded overview | Under the first question | Citation buttons | Source cards |
|---|---|---|---|---|---|
| 2026-10-15 batch run, `data/demo-ws-v0.11.7a2-warm-profile/serps.json` (45 SERPs, local) | 37 | 31 | 31 | 168 | 209 |
| Fixture corpus, `tests/fixtures/serps.json.bz2` (with plan 060's fixtures) | 77 | 2 | 2 | 10 | 12 |

Example: `ef30639b2b33` ("why is the sky blue"). Its PAA's first question, "Why
is the sky blue a simple answer?", holds a lede, a "How It Works" section, a
"NASA Space Place (.gov) +1" citation, and 7 source cards.

```bash
P=.planners/plans/061-paa-embedded-ai-overview/probe_paa_aio.py
uv run python $P tests/fixtures/serps.json.bz2 --show 2
uv run python $P data/demo-ws-v0.11.7a2-warm-profile/serps.json --show 0   # local run file
```

The two fixture SERPs arrive with plan 060 (PR #203); run against `dev` after it
merges.

**Decide first.** This is a hybrid component: a question list plus one
generated answer. Choose the output shape before writing code:

- (a) Keep one `people_also_ask` row and add the answer to its details (the
  question it answers, text, sections, citations, sources). This needs a
  `details` shape beyond `"text"`. Check it against the details schema rules
  (reuse existing labels, no null-filled payloads).
- (b) Emit the answer as a separate `ai_overview` row at the PAA's `cmpt_rank`
  with its own `sub_rank`, plus a marker that it came from a PAA (e.g. a
  `sub_type`), leaving the PAA row as is.
- (c) Something else that keeps question order and answer provenance.

**Steps.**

1. Pick the shape (above) and record it in this plan.
2. Reuse the plan 060 body and source extraction from
   `WebSearcher/parsers/components/ai_overview.py` (`_extract_body`,
   `_extract_sources`, payload indexing) rather than copying it. Scope source
   cards to the PAA answer, not the whole document.
3. Add a run SERP whose PAA has an answer with sources, if the two fixtures do
   not cover the variety, and coverage tests in `tests/test_parser_coverage.py`
   that fail on current code.
4. Regenerate snapshots. Only the PAA rows of SERPs with an embedded answer may
   change; the PR shows before and after rows.

**Open questions.**

1. Is the answer always under the first question, and is there only one per
   PAA? True for all 31 in the run; check any new captures.
2. Do lazily expanded answers (questions after the first) ever ship in the
   HTML? None seen.

## Log

- **2026-10-16T19:02:51-07:00** — Activated.
  - Branch: `feature/paa-embedded-ai-overview`
  - Base: `dev` at `c045ff7`
  - Worktree: `.worktrees/paa-embedded-ai-overview`
  - PR: pending
- **2026-10-16T19:14:40-07:00** — Shape decided (step 1): option (a), the answer stays inside the people_also_ask row.
  The answer renders inside the PAA box under its first question, so it is part of that component, not a separate overview. A rendered example (ef30639b2b33) showed this.
  PAA rows that carry an answer get `sub_type: "ai_overview"`; rows without one keep `sub_type: null`.
  The answer goes in `details.answer` beside `details.items`, with `question`, `text`, and, when present, `sections`, `citations`, `sources`, `follow_up`, the same fields as the main overview's details. `details.type` stays `"text"`.
  Rejected (b), a separate `ai_overview` row: it would be the first component to emit rows of two types, and it would raise `ai_overview` row counts for 2026-10 SERPs.
- **2026-10-16T19:19:30-07:00** — PR opened: https://github.com/gitronald/WebSearcher/pull/204
- **2026-10-16T19:19:40-07:00** — Steps 2-4 done (PR #204).
  Step 2: `extract_overview(content, scope)` in `ai_overview.py` is now the shared current-DOM path; `parse_ai_overview` and the PAA parser both call it. Main-overview output is unchanged (all its snapshots byte-identical). PAA source cards are scoped to the `data-q` question holding the answer.
  Step 3: no SERP added to the corpus. The two fixtures cover sectioned answers with and without hyperlinks; the one variant they lack, a flat answer (4 of 31 in the run), is covered by a synthetic test. 7 tests added to `tests/test_parser_coverage.py`; all 7 fail on the previous parser (checked by restoring it temporarily).
  Step 4: only the PAA rows of ef30639b2b33 and 42bc62be2985 changed, adding `sub_type` and `details.answer`; row counts and features are unchanged.
  Run check (`data/demo-ws-v0.11.7a2-warm-profile/serps.json`, local): 31 of 37 PAAs carry an answer; all parse with text, 27 with sections, 209 sources (matching the probe's card count), 148 citations (the probe's 168 buttons less the unattributed panel-open buttons the shared helper drops). Every cited id is in the answer's own sources, and no citation labels leak into the text.
  Open question 1: yes for this run; every answer is under the first question and each PAA has at most one. The parser keeps the first answer if a capture ever shows more.
  Open question 2: no lazily expanded answers in the HTML of either corpus.
- **2026-10-16T19:21:12-07:00** — Implemented: 6 commits ahead of `dev`.
- **2026-10-16T20:21:48-07:00** — Review gate run (/code-review medium on PR #204): 3 plausible findings, 0 confirmed, 4 rejected. Review posted to the PR.
  - Review follow-up: raised: `_question_of` walked past the PAA component to any outer `data-q`; `general_questions` carries `details.answer` without the PAA's `sub_type`; skipped answer candidates have citation widgets decomposed before the skip.
  - Actioned (6f36f2d): `parse_answer` iterates the component's question pairs and takes each one's `div.mZJni`, so the lookup is bounded to the component. Regression test `test_paa_answer_bounded_to_question_pairs` fails on the previous parser; snapshots unchanged.
  - Conscious no-ops: the `general_questions` shape (0 such rows in the corpus or the 2026-10 run; its `sub_type` belongs to the general parser) and the mutation before the skip (nothing reads a skipped subtree). Rejected: per-call index rebuild (0.004 ms vs about 20 ms per parse_serp), src-id collisions, and empty `data-q`.

## Retrospective

- Deciding the output shape first (step 1) kept the change small: keeping the answer inside the PAA row avoided a component that emits rows of two types, and left `ai_overview` row counts for 2026-10 SERPs unchanged.
- Pulling `extract_overview` out of plan 060's parser paid off at once. The PAA answer reuses the body, citation, and source code unchanged, and every main-overview snapshot stayed byte-identical, which showed the refactor was safe.
- The review's one actionable finding was structural: an upward `data-q` walk could leave the component. Starting from the question pairs the parser already holds is both bounded and simpler. Prefer walking down from known nodes over walking up from a match.
- The fixture corpus has only 2 embedded answers against 31 in the 2026-10 run. Run-level checks against the local capture caught what the fixtures could not (flat answers, citation and source counts), so keep a run file in the evidence loop for layout-driven plans.
