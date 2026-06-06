---
status: draft
branch:
created: 2026-06-06T01:27:30-07:00
completed:
pr:
---

# Improve knowledge_rhs parser coverage for fact rows and expandable boxes

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
