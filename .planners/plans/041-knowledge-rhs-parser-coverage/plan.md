---
id: 41
slug: knowledge-rhs-parser-coverage
status: active
branch: feature/v0.10.0-knowledge-rhs-coverage
created: 2026-06-06T01:27:30-07:00
concluded:
pr:
---

# Improve knowledge_rhs parser coverage for fact rows and expandable boxes

> **Absorbs retired plan 029** (`029-knowledge-details-schema-alignment.md`,
> retired 2026-06-06). 029 catalogued the cross-parser `details` divergences in
> the knowledge family but was never started; its inventory went stale after the
> RHS restructure (033/041) and its central decision (typed models vs canonical
> dicts) was settled in practice by the "reuse existing labels, no null-filled
> dicts" discipline this plan already follows. The schema-convergence work below
> carries 029's direction forward. See [§ Schema convergence](#schema-convergence-from-retired-plan-029).

The knowledge RHS (right-hand-side) panel parser currently undercaptures structured entity facts (rows with `data-attrid^='kc:/'`) and skips box headings without navigational links. In the fixture corpus (87 SERPs, 18 with RHS panels), queries like "doctor zhivago" yield 8+ unparsed fact rows (director, release date, reviews, box office), and entity panels like "central park new york" have 19 fact rows plus 14 expandable section headings that lack links but carry meaningful titles (e.g., "Cost", "Things to do").

Current code (`WebSearcher/component_parsers/knowledge_rhs.py:102–123`, `_parse_rhs_boxes()`):

```python
def _parse_rhs_boxes(node: Node, start_rank: int = 1) -> list:
    """One ``side_bar`` row per aria-level=2 box (title = heading, links in details)."""
    ...
    for heading in node.css('[role="heading"][aria-level="2"]'):
        ...
        items = _rhs_box_links(heading)
        if not items:
            continue  # <- Skips all boxes with no links
        rows.append({...})
```

Additionally, fact rows under complementary RHS panels are never extracted.

## Plan

1. **Refactor `_parse_rhs_boxes()` to emit rows for fact rows with `data-attrid^='kc:/'`**, dispatching by attrid pattern:
   - `kc:/local/*` (address, phone, hours, business modes) → `details.type = "text"` with label + value pairs
   - `kc:/film/*`, `kc:/music/*`, etc. (ratings, release, director, etc.) → `details.type = "text"`
   - `kc:*/media_actions*`, `kc:*/awards` (with links) → `details.type = "hyperlinks"` (reuse existing pattern)
   - Group facts by semantic row and extract label + value/links into a consistent structure
2. **Preserve aria-level=2 box titles even when they lack links**, storing them as `sub_type="links"` rows with `details = {"type": "text", "items": [{"label": title}]}` or a similar placeholder. Alternatively, fold them into the main panel's `details["facts"]` if they are "Things to know" expansions (check for `iwY1Mb` expander).
3. **Reuse existing `details.type` labels** (text, hyperlinks, panel) — do NOT invent null-filled dicts. For fact rows without a natural label, use inline extraction: `{"type": "text", "items": [{"label": "<attrid label>", "value": "<extracted text>"}]}` or similar flat schema already seen in `people_also_ask.py` (text items).
4. **Update parser snapshots** in `tests/__snapshots__/` and verify no regressions in the `test_corpus_integrity.py` gate (every parsed record must still yield `features.main_layout` and at least one result).

## Schema convergence (from retired plan 029)

Beyond coverage, reconcile the `details`-shape divergences across the knowledge
family that retired plan 029 catalogued. These are still present in the code and
are the unique value 029 carried; address them here while the RHS parser is
already being touched.

**Divergences to resolve (still live as of 2026-06-06):**

1. **`img_url` (str) vs `img_urls` (list).** `knowledge.py` emits singular
   `img_url`; `knowledge_rhs.py` emits plural `img_urls`. Converge — keep the
   plural list and represent the singular case as a 1-element list so no
   information is lost.
2. **Always-emit vs `None`.** `knowledge.py` always emits a `details` dict;
   `knowledge_rhs.py` emits `details=None` when empty. Pick one (the
   drop-hollow-payloads discipline favors `None` over a null-filled dict).
3. **`heading` vs `subtitle` placement.** Reconcile where the panel title lands.
4. **`text` in `details` vs `parsed["text"]`.** The `dictionary` sub_type writes
   to both (`knowledge.py:223`); resolve the duplication.
5. **Multiple `details["type"]` tags in one family** (`panel`, `hyperlinks`,
   plus `songs`/`albums`/`events` from kp-wholepage music sections). Keep them
   distinct but documented — do not unify away meaning.

**Non-negotiable rules inherited from 029 (the coverage caveat):**

- **Source code is the spec, not the fixtures.** SERP fixtures are a partial
  witness — several knowledge shapes (e.g. `featured_snippet`, `finance`,
  `calculator`, `election`, `dictionary` legacy paths) have zero or partial
  fixture coverage. A branch with no fixture hit is an unwitnessed real-world
  shape, **not** dead code.
- **Preserve, don't prune.** Never drop or collapse a key/branch because it
  "looks unused" — that is silent information loss in production.
- **Green snapshots ≠ behavior preserved.** Snapshots only bound the witnessed
  subset. Pin every code-only shape with synthetic markup in
  `tests/test_knowledge_dispatch.py` *before* migrating it, and review any
  regenerated snapshot diff line-by-line (regen can mask unintended changes in
  covered cases).

## Evidence

Loaded tests/fixtures/serps.json.bz2 (87 records) and parsed each via `ws.parse_serp()`. Identified:
- 43 total side_bar rows across the corpus; 37 with details, 6 with `details=None`
- 18 queries with RHS panels; breakdown of unparsed content:
  - `fact_rows_*`: 9 queries carry kc:/ fact rows (1–19 per query): "doctor zhivago" (8), "central park new york" (19), "footloose cast" (6), "prouve" (6), etc.
  - `aria_level2_boxes_*`: 13 queries have [role=heading][aria-level=2] boxes; many lack links and are skipped (e.g., "Cost Central Park cost", "Things to do what is Central Park famous for")
- Spot-check "central park new york": 19 kc:/ fact rows (address, business modes, unified actions, etc.) are completely unparsed; 14 aria-level=2 headings exist but only 6 are emitted as side_bar rows (those with links). The missing 8 link-less boxes ("Popular Times", "Cost", "Things to do") carry no links but carry meaningful titles.

Reproducible example:

```bash
uv run python << 'EOF'
import bz2
from pathlib import Path
import orjson
import WebSearcher as ws
from WebSearcher._slx import make_soup

FIXTURE = Path("tests/fixtures/serps.json.bz2")
with bz2.open(FIXTURE, "rt") as f:
    records = [orjson.loads(line) for line in f]

target = "doctor zhivago"
for rec in records:
    if rec.get("qry") == target:
        doc = make_soup(rec["html"])
        rhs = doc.css_first("[role=complementary]")
        fact_rows = list(rhs.css("[data-attrid^='kc:/']")) if rhs else []
        print(f"{target}: {len(fact_rows)} fact rows (unparsed)")
        for row in fact_rows[:3]:
            attrid = row.attributes.get("data-attrid")
            print(f"  - {attrid}")
        
        parsed = ws.parse_serp(rec["html"])
        rhs_rows = [r for r in parsed["results"] if r.get("type") == "side_bar"]
        print(f"  Parsed: {len(rhs_rows)} side_bar rows")
EOF
```

Output: "doctor zhivago": 8 fact rows (unparsed); parsed 4 side_bar rows (main + 3 links boxes).

## Acceptance

- [ ] All `kc:/` fact rows are extracted and emitted as side_bar rows with `details.type = "text"` (label + value pairs) or `"hyperlinks"` (for rows with links).
- [ ] aria-level=2 box headings without links are **either** emitted as text-only rows (`details.type = "text"`) **or** folded into the main panel (consensus TBD with review).
- [ ] Snapshot tests updated; no regressions in parser output (main_layout and result count unchanged for existing queries).
- [ ] Fixture corpus reparse confirms fact_rows_* and unparsed aria_level2_boxes_* gaps closed (via ad-hoc scripts verifying counts before/after).
- [ ] Code change is additive and does not invent new `details.type` labels beyond text/hyperlinks/panel/ratings (existing set).
- [ ] (from 029) `img_url`/`img_urls` converged to a single shape (plural list; singular → 1-element list) with no information loss.
- [ ] (from 029) Empty-`details` policy unified across `knowledge.py` and `knowledge_rhs.py` (drop hollow payloads — `None`, not a null-filled dict).
- [ ] (from 029) `dictionary` `text` double-write (`details["text"]` + `parsed["text"]`) resolved.
- [ ] (from 029) Every code-only `details` shape touched is pinned with synthetic markup in `tests/test_knowledge_dispatch.py` before migration; regenerated snapshots reviewed line-by-line.

## Log

### 2026-06-10 — Re-grounded against the post-045 tree at activation

Plan 045 (two-tier result schema, PR #164) merged after this draft was written.
Re-verified the evidence against the current pipeline before starting; the plan
survives with targeted amendments rather than a redesign:

- **Coverage gap intact.** `kc:/` fact rows still completely unparsed; the
  link-less box skip is still at `_parse_rhs_boxes()` (`if not items: continue`).
  Evidence correction: the corpus reparse finds **8** fact-row queries, not 9
  ("central park new york" 19, "doctor zhivago" 8, "prouve" 6, "footloose cast"
  6, "books by roger ebert" 4, "cngress usa" 2, "@nytimes" 2, "alicia keys new
  york lyrics" 1).
- **All four 029 divergences still live** in `knowledge.py` (singular `img_url`
  including a null-filled `img_url: None` write; unconditional `details`
  emission; `heading` vs `subtitle`; dictionary `text` double-write).
- **Divergence #2 is now decided, not open.** 045 settled the empty-`details`
  policy project-wide: `None` on clean rows, only-when-informative, pinned by
  `tests/test_details_schema.py`. The work item becomes "conform `knowledge.py`
  to the 045 contract" — its always-emit pattern and null-filled `img_url` are
  contractually wrong, not just inconsistent.
- **New constraint:** every `details` shape this plan emits must pass the
  `tests/test_details_schema.py` contract (reserved metadata keys `error` /
  `visible` / `timestamp`; top level limited to core fields).
- **Scope addition from 045's retrospective:** knowledge's typeless
  content-details now get a generic `type: "item"` backfill via the
  `BaseResult` validator; giving them semantic types folds into this plan's
  convergence pass. `"item"` now counts as part of the existing-labels set in
  the acceptance criteria.
