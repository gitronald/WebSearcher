---
status: done
branch: update/extractor-position-tracking
created: 2026-02-22T12:56:12-08:00
completed: 2026-02-06T14:14:25-08:00
pr: https://github.com/gitronald/WebSearcher/pull/95
---

# Refactor FeatureExtractor into own file with dataclass

## Context

`FeatureExtractor` currently lives in `parsers.py` alongside `parse_serp()`. It's a static class that returns a plain dict with 8 keys. Moving it to its own module and adding a dataclass for the output aligns it with the existing model patterns in `models/data.py` (which already has `BaseResult`, `BaseSERP`, `DetailsItem`).

### Relationship to extractors/

The `extractors/` package extracts **components** — DOM elements that get classified and parsed into results via `ComponentList`. Each extractor targets a page section (header, main, footer, rhs) and feeds components into the shared pipeline. `FeatureExtractor` is different: it extracts **page-level metadata** (result count, language, notices, overlays) and doesn't use `ComponentList`. It stays as a top-level module alongside `parsers.py` rather than going into `extractors/`.

### Relationship to NoticeParser

`component_parsers/notices.py` handles an inline notice variant with sub_type `location_use_precise_location` — this parses `id="oFNiHe"` notice components containing "Use precise location" + "Results for" text. The `overlay_precise_location` feature detects a different element: the `id="lb"` modal popup asking for device GPS access. In practice the inline notice div is empty when the overlay is present. These are complementary signals at different levels (SERP feature vs component result). No changes needed to `NoticeParser`.

## Changes

### 1. Create `WebSearcher/models/features.py`

Add a `SERPFeatures` dataclass (matching the `DetailsItem` pattern in `models/data.py`):

```python
@dataclass
class SERPFeatures:
    result_estimate_count: float | None = None
    result_estimate_time: float | None = None
    language: str | None = None
    notice_no_results: bool = False
    notice_shortened_query: bool = False
    notice_server_error: bool = False
    infinity_scroll: bool = False
    overlay_precise_location: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
```

### 2. Create `WebSearcher/feature_extractor.py`

Move `FeatureExtractor` class from `parsers.py` to its own module. Update `extract_features()` to return `SERPFeatures` instead of a plain dict.

### 3. Update `WebSearcher/parsers.py`

- Remove `FeatureExtractor` class
- Import from new module: `from .feature_extractor import FeatureExtractor`
- Call `.to_dict()` on the return value at line 38 so `parse_serp()` still returns a plain dict (preserving downstream JSON serialization in `searchers.py` and test snapshots)

### 4. Update `WebSearcher/__init__.py`

Change import path:
```python
from .feature_extractor import FeatureExtractor
```

## Files modified

| File | Action |
|------|--------|
| `WebSearcher/models/features.py` | **Create** - `SERPFeatures` dataclass |
| `WebSearcher/feature_extractor.py` | **Create** - `FeatureExtractor` class (moved from parsers) |
| `WebSearcher/parsers.py` | **Edit** - Remove class, import from new module, `.to_dict()` call |
| `WebSearcher/__init__.py` | **Edit** - Update import path |

## Verification

- `poetry run pytest` - all 18 tests pass with no snapshot changes
- `poetry run python -c "import WebSearcher as ws; print(ws.FeatureExtractor)"` - import works
- `poetry run python -c "from WebSearcher.models.features import SERPFeatures; print(SERPFeatures())"` - dataclass works
