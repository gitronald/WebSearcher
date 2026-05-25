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
