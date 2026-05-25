---
status: active
branch: feature/reclassify-general-blocks
created: 2026-05-25T00:37:41-07:00
completed:
pr:
---

# Reclassify people-also-ask / image-filter blocks out of `general`

Deferred from plan 024 phase 5. Diagnosis captured while the context was fresh;
implementation is a classifier change that needs corpus-wide validation, so it
was split out rather than rushed into the parser-coverage branch.

## Plan

### Problem

A downstream reparse audit flagged `general` extraction errors: ~14,794 rows
(~1.7% of `general`) with `sub_type=null` and `title`/`url`/`text`/`cite` all
null (`error="no title or url"`). Low rate but real.

These are **not** broken general results — they are non-general blocks
**misclassified as `general`**: "People also ask" blocks (`div.MjjYud`) and
image / "guided search filters" packs (`div.ULSxyf`) that land in the `general`
parser, hit `find_subcomponents`' whole-component fallback, and emit a hollow
row.

**Repro** (fixtures already exist from plan 024 — no new fixtures needed):

`tests/fixtures/serps-parser-coverage.json.bz2`
- `men's old school wears` — 4 hollow `general` rows (a `MjjYud` PAA block +
  `ULSxyf` image/filter blocks)
- `kaka boots` — 2 hollow `general` rows

Write a small script (avoid heredoc braces per CLAUDE.md) that loads the fixture
and counts `general` rows where `sub_type`, `title`, `url`, `text`, `cite` are
all null; today that yields 4 and 2 respectively.

### Root cause (verified in plan 024)

- `classifiers/main.py` `ClassifyMain.general` matches `MjjYud` directly
  (`format-03`: `any(s in ["hlcw0c", "MjjYud", "PmEWq"] for s in class)`,
  ~line 187). `MjjYud` is a **deliberate, load-bearing** general marker, also
  used by `img_cards` (~line 211) and adjacent to `general_questions`.
- In the classify chain (`ClassifyMain.classify`, ~line 101), `general`
  (position ~125) runs **before** `people_also_ask` (~126), so a `MjjYud` PAA
  block is claimed by `general` first.
- `ClassifyMain.people_also_ask` (secondary, ~line 304) only matches classes
  `["g", "kno-kp", "mnr-c", "g-blk"]`; the primary PAA detection is header-text
  in `ClassifyMainHeader.classify`. Neither catches these `MjjYud` PAA blocks.
- The `ULSxyf` image/filter block also resolves to `general` (likely via
  `general` `format-04` = a nested `div.g`, or the `ULSxyf`-adjacent paths used
  by `banner`/`images`) — **confirm the exact path during implementation.**
- **Not fixable in the general parser:** `components.py:104` replaces any empty
  parser output with a `"no subcomponents parsed"` error row, so dropping the
  hollow rows inside `parse_general_results` just swaps one error for another.
  The fix must be in the classifier.

### Approach

Route these blocks to the correct type *before* `general` claims them, without
disturbing legitimate general-result detection (the hard part — `MjjYud` is
shared):

1. **People also ask (`MjjYud`).** Detect the PAA nature of the block — e.g. a
   "People also ask" / localized heading within it, or a PAA-specific structural
   marker (related-question rows) — and classify it `people_also_ask`. Decide
   whether to extend `ClassifyMain.people_also_ask` (and move it ahead of
   `general` in the chain for the matching precondition) or to add a guard so
   `general` returns `unknown` for blocks whose only general signal is `MjjYud`
   but which carry a PAA heading.
2. **Image / guided-search-filter (`ULSxyf`).** Route to `images` (or a
   dedicated filters type) once the exact current classification path is
   confirmed. Reuse the existing `images` `ULSxyf` handling (~line 247) where
   possible.
3. Preserve `MjjYud`-based general detection for genuine general results.
   Whatever discriminates "PAA/image block" from "general result" must be a
   *positive* signal on the block (heading text / structural marker), not the
   mere presence/absence of `MjjYud`.

### Validation (mandatory — this is why it was deferred)

- **No regression on legitimate `general`.** Re-parse the `serps-v*` snapshot
  fixtures; the `general` results must be unchanged (run the snapshot suite —
  the 19 `panel`/general-bearing SERPs are the guard). Any change to a real
  general result is a regression.
- **Corpus check, not just fixtures.** Reparse a broad sample (the plan-024
  parser-issues sample and/or a directives crawl) and compare type-count deltas:
  `general` should drop by ~the hollow-row count, `people_also_ask` / `images`
  should rise correspondingly, and total `unknown` / error rows should fall. No
  large unexplained reclassification of other types.
- **Fixture assertions.** `men's old school wears` and `kaka boots` should yield
  **0** hollow `general` rows; the PAA/image blocks should appear under their
  correct types. Add coverage tests alongside the plan-024
  `tests/test_parser_coverage.py` cases.

### Success criteria

- 0 hollow `general` error rows on the two fixtures (and across the sample).
- PAA blocks typed `people_also_ask`, image/filter blocks typed `images`.
- `serps-v*` snapshots: no change to any genuine `general` result.
- Classifier-order rationale documented (CLAUDE.md notes the chain order is
  significant — `available_on` precedence over `knowledge_panel` is precedent).

### Out of scope

- Parsing/enriching the PAA or image blocks beyond correct classification (their
  existing parsers handle content once routed correctly).
- The `general` video/subtype `elif` chain in `general.py` (unrelated).

## Log

### 2026-05-25 — corrected diagnosis (the original spec above was wrong)

Reproducing the hollow rows and dumping the raw HTML of every offending block
(saved to `data/tmp_025/`, gitignored) showed the original diagnosis is
**incorrect**: these are **not** "People also ask" (`MjjYud`) or image/filter
(`ULSxyf`) blocks. They are **organic shopping packs** — product grids and
"Explore brands" merchant carousels — that slip into `general` via `format-03`
(`MjjYud`/`hlcw0c` root class) or `format-04` (nested `div.g`/`Ww4FFb`). Every
hollow block carries product names, prices, stores, and ratings.

Corpus scan (all `serps-*.json.bz2`): 29 hollow `general` components — 27 in the
coverage fixture, 2 in the `serps-v0.7.2-ads` snapshot corpus (`gu gels`). The
candidate static signals from the original plan do not separate them:
`no yuRUbf/rc` catches all 29 but mis-fires on 45 genuine general results;
the obfuscated shopping classes (`RDApEe`/`Y0A0hc`/...) hit 140 genuine general
results. So a class-only guard is unsafe.

### 2026-05-25 — approach (scoped to `men's old school wears` first)

Decision (with the maintainer): route both shopping families to the existing
but unimplemented `products` type, with sub_types `grid` and `brands`. The
product grids are JS-driven and carry **no links**, so their rows are
title + `ratings` details (price/store/rating) with `url=None` — confirmed no
href or url-bearing data-attribute is recoverable.

Stable, corpus-clean signals (0 false positives on genuine general):
- **grid** — each product is a `data-attrid="apg-product-result"` card.
- **brands** — a `role=heading` "Explore brands" carousel.

Changes:
- `classifiers/main.py`: new `ClassifyMain.products`, placed **before**
  `general` in the chain, precondition `product-viewer-group`/`g-more-link` in
  the component's tag names.
- `component_parsers/products.py`: new `parse_products` (grid + brands),
  reusing the `ratings` details schema from `shopping_ads`.
- registered in `component_parsers/__init__.py`; `products` type gains
  `sub_types=("grid", "brands")` in `component_types.py`.
- `tests/test_parser_coverage.py`: `test_products_no_hollow_general`,
  `test_products_brands_carousel`, `test_products_grid`.
- regenerated the `gu gels` snapshot (its "Explore brands" block now parses to
  `products`/`brands`).

Result on `men's old school wears`: 4 hollow `general` rows -> 0; 27 populated
`products` rows (3 brands + 24 grid); the 7 genuine `general` results unchanged.

### 2026-05-25 — follow-on: `general` `image_strip` sub_type

While reviewing the same SERP, several genuine `general` results were found to
carry a horizontal strip of `<g-img>` thumbnail previews (wrapper
`div.d86Vh.KUuaG`) — e.g. Pinterest boards, Etsy markets, shop category pages.
These already parsed correctly (title + url + cite); this adds a `sub_type`
flag. The thumbnails are JS-driven `data:` placeholders with no per-image url
or alt text, so the probe found nothing that fits an existing details schema —
only a thumbnail count — so `details` is left `None` (per the details-schema
discipline). Change: detect the wrapper in `parse_subtype_details`
(`general.py`), add `image_strip` to the `general` `sub_types`, plus
`test_general_image_strip_subtype`. Corpus-wide: 10 `image_strip` rows, all
still carrying a url (pure enrichment); regenerated the `taylor swift` and
`gu gels` snapshots.

### 2026-05-25 — broader corpus closed out (0 hollow rows corpus-wide)

Resolved the remaining 22 (the "Still open" note below is now superseded).

- **Older-markup product grids (20 rows).** They share `<product-viewer-group>`
  with the modern grids but use `g-inner-card` cards (no `apg-product-result`)
  with the same inner field classes. Extended `ClassifyMain.products` to also
  match `product-viewer-group` + `g-inner-card`, and `parse_products` to fall
  back to `g-inner-card`. Corpus-validated: `product-viewer-group` alone also
  appears in 7 `local_results` packs (which have no `g-inner-card`), so the
  `g-inner-card` conjunct is required to avoid stealing them — 0 false
  positives. Tests: `test_products_grid_older_markup`.
- **Two non-product widgets → two new types.** `most_read_articles` (editorial
  article carousel; classified by the "Most-read articles" header text — a
  corpus scan confirmed no other heading maps to the same unclassified
  carousel) and `buying_guide` (faceted accordion; "Buying guide" header text,
  one row per `div.ITWcLb` label→question facet). Tests: `test_most_read_articles`,
  `test_buying_guide`.

### 2026-05-25 — follow-on: `promo` type (deals banner, was extractor-dropped)

A "Save with deals on apparel, electronics, and more / Shop deals" banner
(`div.ULSxyf` wrapping `<promo-throttler>`) was being **dropped by the extractor**
(`is_valid`), not misclassified. The maintainer opted to capture it as a
shopping-intent signal (`promo` / `sub_type=shopping`). The `is_valid` guard was
too broad — it also dropped the `central park new york` main-results wrapper
(same `ULSxyf`+`promo-throttler`, but **with** `div.g` results). Discriminator:
the deals banner has **no `div.g`** (the wrapper has 7). Narrowed `is_valid` to
drop only the `div.g`-bearing wrapper (central park unchanged), keeping pure
promo banners for classification; added `ClassifyMain.promo` (anchored on the
stable `<promo-throttler>` tag, not the localizable "Shop deals" text) and
`parse_promo`. Tests: `test_promo_shopping_banner`, plus updated
`test_is_valid_*` to pin the new keep/drop behavior.

**Result: 0 hollow `general` rows corpus-wide** (was 29). New-type row counts
across fixtures: products 206, promo 8, buying_guide 8, most_read_articles 3.
No snapshot changes from this batch (all new types occur only in the coverage
fixture; central park's wrapper still drops).

### Still open (broader corpus, deferred) — SUPERSEDED 2026-05-25

`apg-product-result` + "Explore brands" cover 7 of the 29 corpus-wide hollow
blocks. The other 22 (e.g. `red skin peanuts`, `file folder`, `prouve`,
`kelly kettle`, plus the `gu gels` rank-5 grid) are **older-markup** product
grids without `apg-product-result`, and two are non-product widgets
("Most-read articles", "Buying guide: Graphics Tablets"). Extending the
`products` signals/parser to those markups is follow-up work.
