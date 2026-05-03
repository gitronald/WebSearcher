---
status: done
branch: dev
created: 2026-02-22T12:56:12-08:00
completed: 2026-02-05T14:12:41-08:00
pr: https://github.com/gitronald/WebSearcher/pull/94
---

# Ads Parser Format vs Other Component Parsers

## Summary

The refactored `ads.py` now follows a distinct structural pattern compared to other parsers. This documents the key differences as a reference for applying the same pattern elsewhere.

---

## Ads.py Pattern (Refactored)

### 1. Nested function structure

Each sub-type parser is a public function containing private nested helpers:

```python
def parse_ad_secondary(cmpt: bs4.element.Tag) -> list:

    def _parse_ad_secondary(cmpt):
        subs = cmpt.find_all(...)
        return [_parse_ad_secondary_sub(sub, sub_rank) for ...]

    def _parse_ad_secondary_sub(sub, sub_rank) -> dict:
        return BaseResult(...).model_dump()

    def _parse_ad_secondary_sub_details(sub) -> list:
        ...

    return _parse_ad_secondary(cmpt)
```

### 2. BaseResult construction

Returns `BaseResult(...).model_dump()` instead of raw dicts:

```python
# ads.py
return BaseResult(
    type='ad',
    sub_type='secondary',
    sub_rank=sub_rank,
    title=webutils.get_text(...),
    ...
).model_dump()
```

### 3. DetailsItem dataclass for structured details

Uses `DetailsItem` from `models/data.py` with `asdict()`:

```python
details_list = [asdict(DetailsItem(url=url)) for url in urls]
```

### 4. Classify-then-dispatch pattern

Separates classification from parsing with a dispatch dict:

```python
def parse_ads(cmpt):
    subtype_parsers = {
        'legacy': parse_ad_legacy,
        'secondary': parse_ad_secondary,
        ...
    }
    sub_type = classify_ad_type(cmpt)
    if sub_type in subtype_parsers:
        return subtype_parsers[sub_type](cmpt)
```

### 5. Namespace imports and type hints

```python
from .. import webutils
def parse_ads(cmpt: bs4.element.Tag) -> list:
```

---

## Other Parsers Pattern (Current)

### `general.py` - Ad-hoc dicts, direct imports

- Returns raw dicts: `{'type': 'general', 'sub_rank': sub_rank, ...}`
- Direct imports: `from ..webutils import get_text, get_link`
- No type hints on parameters (just `cmpt`, `sub`)
- Flat function structure (no nesting)
- Details built as a mutable dict, populated conditionally
- Local helpers (`parse_alink`, `parse_ratings`) at module level

### `videos.py` - Ad-hoc dicts, namespace imports

- Returns raw dicts with mutable post-processing
- Namespace imports: `from .. import webutils`
- Partial type hints (`sub_type: str`)
- Flat function structure
- Local helpers (`get_url`, `get_img_url`) at module level
- Changelog in docstring

---

## Key Differences

| Feature | `ads.py` | Other parsers |
|---------|----------|---------------|
| Return type | `BaseResult(...).model_dump()` | Raw `dict` |
| Details values | `DetailsItem` dataclass | Raw dicts/lists |
| Function structure | Nested (private helpers inside public) | Flat (all module-level) |
| Dispatch | Dict-based dispatch | Inline conditionals |
| Classification | Separate `classify_*` function | Inline or implicit |
| Imports | `from .. import webutils` | Mixed |
| Type hints | Full (`bs4.element.Tag`, `-> list`) | Partial or none |
| Changelog | Module docstring | Some have it, some don't |

---

## Notes

- The `BaseResult.model_dump()` approach provides validation at parse time, catching schema issues early
- The nested function pattern keeps sub-type parsing self-contained and avoids polluting the module namespace
- The `DetailsItem` dataclass provides a consistent structure for detail items (url, title, text) rather than ad-hoc dicts
- See `ad-parser-structure.md` for the canonical nested function template
- See `component-parsers-update.md` for the full migration plan
