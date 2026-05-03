---
status: done
branch: dev
created: 2026-03-15T12:17:07-07:00
completed: 2026-03-15T16:23:47-07:00
pr: https://github.com/gitronald/WebSearcher/pull/100
---

# Standardize Data Models

Unify the codebase on Pydantic BaseModel, add typed models for currently untyped data, and tighten the parsing pipeline so types flow through instead of being discarded and reconstructed.

## Current Problems

1. Mixed model systems (Pydantic, dataclass, plain dict) with no clear rationale
2. `parse_serp()` returns a plain dict — no typed model for combined output
3. Component parsers return `list[dict]`, validated late via `BaseResult(**dict).model_dump()` round-trip
4. `SERPFeatures` and `DetailsItem` are dataclasses while peer models are Pydantic
5. Three serialization methods: `.model_dump()`, `.to_dict()`/`asdict()`, manual dict construction
6. `details: Any | None` on BaseResult — no type safety for nested structures
7. Searcher `response_output` is an untyped dict
8. No model for the full parsed SERP (metadata + features + results)

## Changes

### Phase 1: Standardize on Pydantic

Convert dataclasses to Pydantic BaseModel so everything uses `.model_dump()`.

#### 1a. Convert SERPFeatures to Pydantic

**File:** `models/features.py`

- Change from `@dataclass` to `BaseModel`
- Remove `to_dict()` method (use `.model_dump()` instead)
- Update caller in `feature_extractor.py`: `.to_dict()` -> `.model_dump()`
- Update caller in `parsers.py`: `.to_dict()` -> `.model_dump()`
- Update test assertions in `test_feature_extractor.py`

#### 1b. Convert DetailsItem to Pydantic

**File:** `models/data.py`

- Change from `@dataclass` to `BaseModel`
- Remove `to_dict()` method
- Remove `from dataclasses import asdict, dataclass, field`

#### 1c. Simplify DetailsList (deferred to Phase 4)

Moved to Phase 4. The `DetailsList.to_dicts()` call sites are the same sites that Phase 4 wraps in typed dicts. Doing both in one pass avoids editing each call site twice.

### Phase 2: Add missing models

#### 2a. Add ResponseOutput model

**File:** `models/data.py`

```python
class ResponseOutput(BaseModel):
    html: str = ""
    url: str = ""
    user_agent: str = ""
    response_code: int = 0
    timestamp: str = ""
```

**Update callers:**
- `search_methods/selenium_searcher.py`: return `ResponseOutput(...)` instead of dict
- `search_methods/requests_searcher.py`: return `ResponseOutput(...)` instead of dict
- `searchers.py`: use `.model_dump()` when merging into BaseSERP construction

#### 2b. Add ParsedSERP model

**File:** `models/data.py`

```python
class ParsedSERP(BaseModel):
    crawl_id: str = ""
    serp_id: str = ""
    version: str = ""
    method: str = ""
    features: dict = Field(default_factory=dict)
    results: list[dict] = Field(default_factory=list)
```

**Update callers:**
- `searchers.py:parse_serp()`: construct `ParsedSERP` instead of merging dicts into `self.parsed`
- `searchers.py:save_parsed()`: use `.model_dump()` for serialization
- `searchers.py:save_results()`: access `.results` attribute instead of dict key

Note: `features` and `results` stay as dicts for now. Phase 3 tightens these.

### Phase 3: Standardize parser return convention

All component parsers should return `list[dict]`. The centralized `add_parsed_result()` in `components.py` handles BaseResult validation — parsers don't need to.

#### 3a. Remove BaseResult construction from ads.py (done)

`ads.py` was the only parser that constructed `BaseResult(...).model_dump()`, creating a redundant double round-trip through BaseResult (once in the parser, once in `add_parsed_result()`). Converted all instances to plain dict returns, matching every other parser.

#### 3b. Add section/cmpt_rank/serp_rank to BaseResult (optional)

Consider whether `section`, `cmpt_rank`, and `serp_rank` should be fields on `BaseResult` rather than merged in at export. This would let `export_component_results()` return `list[BaseResult]` all the way through.

```python
class BaseResult(BaseModel):
    section: str = "unknown"
    cmpt_rank: int = 0
    serp_rank: int = 0
    sub_rank: int = 0
    type: str = "unclassified"
    # ... rest of fields
```

Pro: single model all the way through, matches test EXPECTED_KEYS exactly.
Con: section/cmpt_rank set at Component level, not parser level — two-stage initialization.

### Phase 4: Consolidate details field

Consolidate `details` to always be `dict | None`. Every details dict gets a `type` key for self-describing structure. Also removes `DetailsList`/`DetailsItem` (deferred from Phase 1c) since the same call sites change.

See plan 001 log (2026-03-15) for the full spec: type definitions, per-parser mappings, and before/after for every call site.

#### 4a. Remove DetailsList, wrap in typed dicts

Replace `DetailsList.to_dicts()` calls with typed dict construction. Each call site goes from returning a bare list to returning a dict with `type` and `items` keys.

**Callers to update** (all in `component_parsers/`):
- `ads.py` — menu -> `"menu"`, sitelinks -> `"links"`, legacy/local_service -> `"text"`
- `general.py` — submenu links -> `"hyperlinks"`
- `knowledge.py` — urls already in dict, add `type` key
- `knowledge_rhs.py` — main: add `type`, subs: wrap list -> `"hyperlinks"`
- `top_image_carousel.py` — wrap list -> `"hyperlinks"`
- `available_on.py` — wrap list -> `"providers"`, flatten `misc.cost` to `cost`
- `footer.py` — wrap list -> `"hyperlinks"`

#### 4b. Wrap non-DetailsItem cases

- `searches_related.py` — `list[str]` -> `{"type": "text", "items": [...]}`
- `people_also_ask.py` — `list[str]` -> `{"type": "text", "items": [...]}`
- `twitter_result.py` — `str` -> `{"type": "tweet", "url": "..."}`

#### 4c. Add type key to existing dicts

- `general.py` (rating, product, video) — add `"type"` key
- `knowledge.py` — add `"type": "panel"`
- `knowledge_rhs.py` main — add `"type": "panel"`
- `local_results.py` — add `"type": "ratings"`
- `shopping_ads.py` (hotels) — add `"type": "ratings"`

#### 4d. Tighten BaseResult.details

Change `details: Any | None` to `details: dict | None` on BaseResult.

#### 4e. Remove DetailsItem and DetailsList

After all call sites are updated, remove `DetailsItem`, `DetailsList`, and their imports from `models/data.py` and all component parsers.

## Implementation Order

1. **Phase 1a, 1b** — convert SERPFeatures and DetailsItem to Pydantic (mechanical, no output change)
2. **Phase 2a** — ResponseOutput model (no output change)
3. **Phase 2b** — ParsedSERP model (no output change)
4. **Phase 3a** — done (removed BaseResult from ads.py)
5. **Phase 3b** — evaluate after phases 1-2
6. **Phase 4** (4a-4e) — details consolidation (breaking output change, update snapshots)

Phase 1c is deferred to Phase 4 (same call sites). Each phase should be a separate commit. Phase 4 can be split into multiple commits by sub-phase.

## Tests

- Phases 1-3: existing snapshot tests validate output stays identical
- Phase 1a, 1b: unit tests (`test_models.py`, `test_feature_extractor.py`) need updates for `.to_dict()` -> `.model_dump()`
- Phase 4: **breaking output change** — snapshot tests must be updated to reflect new details structure
- Run full test suite after each phase to catch regressions

## Log

### 2026-03-15

Completed phases 1a, 1b, 2a, 2b, and 3a. All output-preserving refactors — 178 tests passing, 62 snapshots unchanged.

| Phase | Commit | Summary |
|-------|--------|---------|
| 3a | `25ddd60` | remove BaseResult construction from ads parser |
| 1a | `40bbe12` | convert SERPFeatures from dataclass to pydantic |
| 1b | `b203653` | convert DetailsItem from dataclass to pydantic |
| 2a | `4cc5091` | add ResponseOutput model for search method returns |
| 2b | `a9a96fe` | add ParsedSERP model for parsed output |

Problems resolved: #1 (mixed model systems), #2 (untyped parse_serp output), #4 (dataclass/pydantic mix), #5 (three serialization methods), #7 (untyped response_output), #8 (no parsed SERP model).

Remaining: #3 (BaseResult round-trip, Phase 3b), #6 (details typing, Phase 4).

Completed Phase 4 (4a-4e) in a single commit. Breaking output change — 61 snapshots updated, 174 tests passing.

| Phase | Commit | Summary |
|-------|--------|---------|
| 4a-4e | `9d6deda` | consolidate details field to typed dicts, remove DetailsItem/DetailsList |

Changes per file:
- **ads.py**: DetailsList/DetailsItem removed. Menu → `{"type": "menu", "items": [...]}`, sitelinks → `{"type": "links", "items": [...]}`, legacy/local_service text → `{"type": "text", "items": [...]}`
- **general.py**: submenu links → `{"type": "hyperlinks", "items": [...]}`, rating → `{"type": "review", ...}`, product → `{"type": "product", ...}`, video → `{"type": "video", ...}`
- **knowledge.py**: urls now plain list of dicts, added `"type": "panel"` to details
- **knowledge_rhs.py**: main details gets `"type": "panel"`, sub details → `{"type": "hyperlinks", "items": [...]}`
- **top_image_carousel.py**: → `{"type": "hyperlinks", "items": [...]}`
- **available_on.py**: → `{"type": "providers", "items": [...]}`, flattened `misc.cost` to `cost`
- **footer.py**: → `{"type": "hyperlinks", "items": [...]}`
- **searches_related.py**: `list[str]` → `{"type": "text", "items": [...]}`
- **people_also_ask.py**: `list[str]` → `{"type": "text", "items": [...]}`
- **twitter_result.py**: `str` → `{"type": "tweet", "url": "..."}`
- **local_results.py**: added `"type": "ratings"` to details dict
- **shopping_ads.py**: added `"type": "ratings"` to hotel details dict
- **models/data.py**: removed DetailsItem, DetailsList; `details: Any | None` → `details: dict | None`; removed `from typing import Any`
- **test_models.py**: removed DetailsItem/DetailsList tests

All problems resolved: #1-#8. Phase 3b skipped (low value, awkward two-stage init).

Follow-up fix: `local_results.py` sub_type normalization. The header element for local results sometimes contains the full location text (e.g. `"Results for Palo Alto, CA 94301"`) spread across child spans. The old code ran `header.lower().replace(" ", "_")` on the concatenated text, producing location-specific sub_types like `"results_for__palo_alto,_ca_94301"`. Fixed to normalize any header starting with "results for" to just `"results_for"`.

| Phase | Commit | Summary |
|-------|--------|---------|
| — | `d76cbe7` | normalize local_results sub_type for "results for" headers |
| — | `3406b2b` | update snapshots for local_results sub_type normalization |

### Commit log

| Commit | Summary |
|--------|---------|
| `25ddd60` | remove BaseResult construction from ads parser |
| `40bbe12` | convert SERPFeatures from dataclass to pydantic |
| `b203653` | convert DetailsItem from dataclass to pydantic |
| `4cc5091` | add ResponseOutput model for search method returns |
| `a9a96fe` | add ParsedSERP model for parsed output |
| `9d6deda` | consolidate details field to typed dicts, remove DetailsItem/DetailsList |
| `d76cbe7` | normalize local_results sub_type for "results for" headers |
| `3406b2b` | update snapshots for local_results sub_type normalization |
