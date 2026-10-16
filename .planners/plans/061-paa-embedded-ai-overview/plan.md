---
id: 61
slug: paa-embedded-ai-overview
status: draft
branch:
created: 2026-10-16T15:06:11-07:00
concluded:
pr:
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
