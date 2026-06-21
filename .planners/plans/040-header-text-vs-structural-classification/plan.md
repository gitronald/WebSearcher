---
id: 40
slug: header-text-vs-structural-classification
status: done
branch: feature/v0.10.0-header-text-dependencies
created: 2026-06-06T01:27:30-07:00
concluded: 2026-06-06T16:24:49-07:00
pr: https://github.com/gitronald/WebSearcher/pull/158
---

# Add structural CSS dispatch path for buying_guide and products to reduce header-text dependency

The component classifier (WebSearcher/classifiers/main.py:103–142) dispatch table relies on header TEXT for many types, so non-English headings or reworded titles miss them. Two key types already have **unique, stable CSS class signals** that would catch any-heading variant:
- `buying_guide` has class `ITWcLb` (WebSearcher/component_parsers/buying_guide.py:16)
- `products` (brands subtype) has class `gON1yc` (WebSearcher/component_parsers/products.py:37)

However, `most_read_articles` **has NO unique structural signal** — it is purely header-text dependent (only "Most-read articles") and cannot be salvaged with a structural dispatch.

Current bottleneck: `ClassifyMainHeader.classify()` (line 107) runs AFTER structural preconditions and relies entirely on header-text matches via the `header_text_to_type()` dictionary. The classifier order puts text-based detection late but still early enough to shadow structural classifiers; a structural-first dispatch for types with unique CSS classes would catch them before text lookup, reducing fragility to localization and HTML variants.

## Plan

1. **Add structural preconditions to the dispatch table** for types with unique CSS signals:
   - Add a precondition `lambda s: "ITWcLb" in s.classes` to `ClassifyMain.buying_guide` call (line 104 or before `ClassifyMainHeader`)
   - Add a precondition `lambda s: "gON1yc" in s.classes` to a new or existing products classifier (augment line 129–131)
   
2. **Extract a dedicated `ClassifyMain.buying_guide()` method** if one doesn't exist:
   - Check if `ClassifyMain.buying_guide()` exists; if not, create it to return `"buying_guide"` when the `ITWcLb` class is present (similar to `ClassifyMain.products()`, lines 360–373)
   
3. **Upgrade `ClassifyMain.products()` to check for gON1yc before header text:**
   - Augment the existing products method (lines 360–373) to detect `gON1yc` (brands carousel) as a structural signal, not just data-attrid or heading text
   
4. **Flag `most_read_articles` as header-text-only** in comments:
   - Mark in the dispatch table (around line 107) that `most_read_articles` has no unique structural signal and remains header-text vulnerable
   
5. **Reorder dispatch entries** (optional, for clarity):
   - Move structural classifiers (`buying_guide`, `products` with preconditions) earlier in the table, before `ClassifyMainHeader` (line 107), to catch them by structure first
   
6. **Update tests** to verify the structural dispatch works:
   - Add or update tests in `tests/test_parser_coverage.py` to confirm `buying_guide` and `products` classify correctly even with header-text mutations

## Evidence

Examined the fixture corpus at tests/fixtures/serps.json.bz2 (87 SERPs, 1,746 total components parsed). Real-world occurrences:

- **buying_guide**: 8 instances found; all carry `ITWcLb` class. Example: "drawing tablet" query. No unique header text pattern (headers are empty or variable).
- **products**: 206 instances; 186 are type "products" (brands carousel with `gON1yc` class, "Explore brands" header or blank). No unique header text guarantees.
- **most_read_articles**: 3 instances; all have header "Most-read articles" (English-only match). Classes: `['ULSxyf']` only — no unique structural marker. If query is localized (e.g., "Articles les plus lues"), the type is unclassifiable.

Fixture distribution (87 SERPs):
- products: 206 results
- buying_guide: 8 results
- most_read_articles: 3 results

## Reproducible example

Save the following as `test_structural_dispatch.py` and run `uv run python test_structural_dispatch.py`:

```python
import bz2
from pathlib import Path
import orjson
from selectolax.lexbor import LexborHTMLParser as HTMLParser
from WebSearcher._slx import get_text

SERPS_PATH = Path('tests/fixtures/serps.json.bz2')
serps = []
with bz2.open(SERPS_PATH, 'rt') as f:
    for line in f:
        serps.append(orjson.loads(line))

print("Structural signal detection (fixture corpus):")
print("=" * 70)

findings = {'ITWcLb': [], 'gON1yc': [], 'most_read': []}

for serp in serps:
    parser = HTMLParser(serp['html'])
    html = parser.root
    main_section = html.css_first('[role="main"]')
    if not main_section:
        continue
    
    for cmpt in main_section.css('div'):
        if 'Z95pIb' in cmpt.attributes.get('class', ''):
            continue
        classes = cmpt.attributes.get('class', '').split()
        heading = cmpt.css_first('[role="heading"]')
        header_text = (get_text(heading) or '').strip() if heading else ''
        
        if 'ITWcLb' in classes:
            findings['ITWcLb'].append((serp['qry'], header_text))
        if 'gON1yc' in classes:
            findings['gON1yc'].append((serp['qry'], header_text))
        if 'Most-read' in header_text:
            findings['most_read'].append((serp['qry'], classes))

print(f"\nITWcLb (buying_guide): {len(findings['ITWcLb'])} instances")
for qry, hdr in findings['ITWcLb'][:2]:
    print(f"  - {qry}: header='{hdr}'")

print(f"\ngON1yc (products/brands): {len(findings['gON1yc'])} instances")
for qry, hdr in findings['gON1yc'][:2]:
    print(f"  - {qry}: header='{hdr}'")

print(f"\nMost-read articles (header-only): {len(findings['most_read'])} instances")
for qry, cls in findings['most_read']:
    print(f"  - {qry}: classes={cls}")
    print(f"    --> NO unique structural signal, vulnerable to localization")
```

## Acceptance

- [ ] `ClassifyMain.buying_guide()` method exists and returns `"buying_guide"` when `ITWcLb` is in component classes
- [ ] Dispatch table at line 103 includes a precondition `lambda s: "ITWcLb" in s.classes` (or the method runs structurally first)
- [ ] `ClassifyMain.products()` detects `gON1yc` class as a structural signal for the brands subtype, separate from header-text logic
- [ ] Dispatch table at line 129–131 includes precondition for `gON1yc` or the products classifier checks it explicitly
- [ ] Code comment added at `most_read_articles` dispatch entry noting it is header-text-only and lacks structural signals (no fix planned, flagged for documentation)
- [ ] Tests updated to confirm `buying_guide` and `products` classify correctly by structure (e.g., with mocked components carrying only the CSS class, no header)
- [ ] All existing snapshot tests pass (no regression in fixture corpus parsing)

## Log

### 2026-06-06 — implementation

Branch `feature/v0.10.0-header-text-dependencies` (off `feature/v0.10.0`).

**Evidence correction.** Re-ran the analysis through the actual extraction +
classification pipeline (not a raw `main_section.css('div')` sweep). The plan's
Evidence counts are **element-level, not component-level**:

| type | plan count | actual components | reality |
| --- | --- | --- | --- |
| buying_guide | 8 | **1** | the 8 were `div.ITWcLb` *rows* inside one component |
| products | 206 | **27** (2 with `gON1yc`) | 25 grid + 2 brands carousels |
| most_read_articles | 3 | **1** | one carousel |

Also, the plan's premise that buying_guide headers are "empty or variable" is
not true for the corpus: the single instance has header `"Buying guide: Graphics
Tablets"`, which the existing English `"Buying guide"` header match already
catches. All three types classify **correctly today** via header text. The
change's value is therefore **robustness to localization/reword**, not fixing a
current miss — so the bar was "add structural-first dispatch with zero corpus
regression," which the 87-snapshot suite confirms.

**Changes (`WebSearcher/classifiers/main.py`):**
1. New `ClassifyMain.buying_guide()` — returns `"buying_guide"` when `div.ITWcLb`
   is present.
2. Dispatch: `buying_guide` entry (precondition `"ITWcLb" in s.classes`) inserted
   **before** `ClassifyMainHeader.classify`, so structure wins over the
   English-only header.
3. `ClassifyMain.products()` gains a `div.gON1yc` structural branch ahead of the
   `"Explore brands"` heading check.
4. Products dispatch precondition broadened with `or "gON1yc" in s.classes` so a
   brands carousel lacking `g-more-link`/`product-viewer-group` still reaches the
   classifier. (`classes` is consulted in full, so no `_NAME_SIGNALS`/`_ID_SIGNALS`
   registration is needed.)

**`most_read_articles`** flagged in two places — its `component_types.py` entry
(source of truth, header-text-only) and a NOTE in the dispatch table. No fix: it
has no unique structural CSS signal.

**Tests** (`tests/test_parser_coverage.py`): four `ClassifyMain.classify` dispatch
tests using constructed components with localized headers + only the structural
class — buying_guide and products/brands classify structurally; the negative
buying_guide case and most_read_articles return non-matching/`unknown`.

**Verification:** full suite `441 passed`, `87 snapshots passed` (no regression);
corpus counts unchanged (buying_guide=1, products=27, most_read_articles=1).

### 2026-06-06 — close / review gate

Ran the `/code-review` gate (xhigh) on `feature/v0.10.0...HEAD`; **no actionable
findings**. The only correctness question — whether `ITWcLb`/`gON1yc` are unique
to their target types, given both now dispatch ahead of the header-text path — is
empirically settled on the corpus (`ITWcLb`→1 buying_guide node, `gON1yc`→2
products nodes), confirmed in source (each class is used only by its own parser),
and snapshot-clean. Accepted as an evidence-backed tradeoff matching the file's
existing `available_on`/`mgAbYb` gate pattern. Checks: `441 passed` / `87
snapshots`, `ruff` clean, `pyrefly` 0 errors. Merged PR #158 into
`feature/v0.10.0`.

## Retrospective

- **The plan's premise was directionally right but its evidence was miscounted.**
  The "8 buying_guide / 206 products / 3 most_read" figures were element-level
  (e.g. 8 `div.ITWcLb` *rows* in one component); the real component counts are
  1 / 27 / 1. Lesson carried forward: validate plan-stage counts through the
  actual extraction+classification pipeline, not a raw `css('div')` sweep.
- **The value was robustness, not a current fix.** All three types already
  classified correctly via English headers in the corpus, so the bar shifted
  from "fix a miss" to "add structural-first dispatch with zero regression" —
  verified by the 87-snapshot suite rather than by new-coverage counts.
- **Structural-first only works where a unique class exists.** buying_guide
  (`ITWcLb`) and products/brands (`gON1yc`) had one; `most_read_articles` did
  not, so it was flagged in-code rather than force-fit. Knowing which types are
  salvageable up front saved effort.
- **Tests target the dispatch, not just the parser.** Constructed components with
  localized headers + only the structural class prove the localization-robustness
  claim directly, which fixture-replay tests (all English) cannot.
