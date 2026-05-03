---
status: done
branch: update/extractor-position-tracking
created: 2026-02-22T12:56:12-08:00
completed: 2026-02-06T15:25:30-08:00
pr: https://github.com/gitronald/WebSearcher/pull/95
---

# Classify "Things to know" as knowledge/things_to_know

## Context

The "Things to know" panel (seen in the "cngress usa" SERP at component rank 5) is currently misclassified as `general`. This happens because `ClassifyHeaderText` runs before the knowledge classifiers in the ordered list, and its `TYPE_TO_H2_MAPPING` maps "Things to know" to `"general"` (`header_text.py:62`). It should be classified as `knowledge` with sub_type `things_to_know`.

## Changes

### 1. Update header text mapping (`WebSearcher/classifiers/header_text.py:56-63`)

Move "Things to know" and "Cosas que debes saber" from the `"general"` list to the `"knowledge"` list.

### 2. Add sub_type detection (`WebSearcher/component_parsers/knowledge.py:105`)

Add a `things_to_know` check before the `else` fallback. Detect via heading text matching "Things to know" or "Cosas que debes saber" (from `details['heading']`).

### 3. Add to cmpt_mappings (`WebSearcher/models/cmpt_mappings.py:77`)

Add `"things_to_know"` to the knowledge sub_types list.

## Files modified

| File | Action |
|------|--------|
| `WebSearcher/classifiers/header_text.py` | **Edit** - Move header text entries from general to knowledge |
| `WebSearcher/component_parsers/knowledge.py` | **Edit** - Add things_to_know sub_type detection |
| `WebSearcher/models/cmpt_mappings.py` | **Edit** - Add things_to_know to sub_types list |

## Verification

- `poetry run pytest` — update snapshots, all tests pass
- Screenshot index 3 of demo data — component 5 should show blue (knowledge) border instead of green (general)
