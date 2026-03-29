---
status: done
branch: parser-updates
created: 2026-02-22T12:56:12-08:00
completed: 2026-02-05T18:58:39-08:00
pr: https://github.com/gitronald/WebSearcher/pull/93
---

# Component Parsers Refactoring Plan

## Overview

This plan analyzes the 28 component parsers in `WebSearcher/component_parsers/` and proposes a standardized structure based on the best patterns observed.

---

## Current Architecture

### Data Flow

```
HTML --> Extractor --> ComponentList
                          |
                          v
                     Component.classify_component()
                          |
                          v
                     Component.select_parser() --> parser_dict[type]
                          |
                          v
                     Component.run_parser(parser_func)
                          |
                          v
                     parser_func(elem) --> list[dict]
                          |
                          v
                     BaseResult(**parsed_result).model_dump()
                          |
                          v
                     Component.result_list
```

### Parser Contract

Each parser receives a `bs4.element.Tag` and must return `list[dict]` where each dict conforms to `BaseResult`:

```python
class BaseResult(BaseModel):
    sub_rank: int = 0
    type: str = 'unclassified'
    sub_type: str | None = None
    title: str | None = None
    url: str | None = None
    text: str | None = None
    cite: str | None = None
    details: Any | None = None
    error: str | None = None
```

---

## Analysis of Current Patterns

### Pattern A: Ad-hoc Dictionary Construction (most common)

**Files**: `general.py`, `videos.py`, `local_results.py`, `twitter_cards.py`, `knowledge.py`, etc.

```python
def parse_video(sub, sub_type: str, sub_rank=0) -> dict:
    parsed = {
        'type': 'videos',
        'sub_type': sub_type,
        'sub_rank': sub_rank,
        'url': get_url(sub),
        'title': webutils.get_text(sub, 'div', {'role':'heading'}),
        'text': webutils.get_text(sub, 'div', {'class':'MjS0Lc'}),
    }
    # ... more logic to add cite ...
    return parsed
```

**Analysis**: This is actually fine! BaseResult fills missing fields with defaults. The only real issue is:
- Extra fields silently dropped (e.g., `timestamp`, `img_url`, `rhs_column`)

---

### Pattern B: Template Copy (`ads.py`)

**Files**: `ads.py`

```python
PARSED = {
    'type': 'ad',
    'sub_type': '',
    'sub_rank': 0,
    'title': '',
    'url': '',
    'cite': '',
    'text': '',
}

def parse_ad(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    parsed = PARSED.copy()
    parsed["sub_type"] = "standard"
    parsed["sub_rank"] = sub_rank
    parsed['title'] = webutils.get_text(sub, 'div', {'role':'heading'})
    # ...
    return parsed
```

**Apparent Benefits**:
- Consistent output schema
- All fields initialized
- Type hints on function signature
- Changelog in docstring

**However**: Research shows this pattern is **unnecessary** - see "Key Insight" below.

---

### Pattern C: Inline Dictionary (compact)

**Files**: `images.py`, `discussions_and_forums.py`, `banner.py`

```python
def parse_image_small(sub, sub_rank=0) -> dict:
    return {
        "type": "images",
        "sub_type": "small",
        "sub_rank": sub_rank,
        "title": get_text(sub, 'div', {'class':'xlY4q'}),
        "url": None,
        "text": None,
    }
```

**Analysis**: Missing fields are fine (BaseResult fills defaults). This pattern works well for simple parsers.

---

### Pattern D: Class-Based (`notices.py`, `footer.py`)

```python
class NoticeParser:
    def __init__(self):
        self.sub_type_text = {...}
        self.parser_dict = {...}

    def parse_notices(self, cmpt) -> list:
        self._classify_sub_type(cmpt)
        self._parse_sub_type(cmpt)
        self._package_parsed()
        return self.parsed_list
```

**Best for**: Complex parsers with many sub-types and classification logic

---

### Pattern E: Delegation/Composition

**Files**: `perspectives.py`, `latest_from.py`, `local_news.py`, `recent_posts.py`, `general_questions.py`

```python
def parse_perspectives(cmpt):
    return parse_top_stories(cmpt, ctype='perspectives')
```

**Benefit**: Code reuse when component types share structure

---

## Identified Issues

### 1. Extra Fields Silently Dropped

Some parsers return extra fields that get silently dropped by `BaseResult`:
- `timestamp` in `view_more_news.py`, `twitter_result.py`, `news_quotes.py`
- `img_url` in `view_more_news.py`
- `rhs_column` in `knowledge_rhs.py`
- `visible` in `ads.py` (filtered before return)

**Decision**: Keep dropping for now - document for future reference (see "Extra Fields - Current Status")

### 2. Code Duplication

See detailed analysis in `component-parser-details-field.md`.

| Function | Files | Consolidate? |
|----------|-------|--------------|
| `parse_alink()` | 4 files | **NO** - each has component-specific behavior |
| `get_img_url()` | 4 files | **PARTIAL** - 3 identical simple versions can consolidate |
| `get_text()` (local) | `knowledge.py` | Rename to avoid shadowing webutils |

**`parse_alink` variations** (NOT identical):
- `general.py`: `a.text`, requires `href`
- `knowledge.py`: `a.get_text('|')` with `|` separator
- `knowledge_rhs.py`: `a.text`, simplest
- `top_image_carousel.py`: checks `href` OR `data-url`, most flexible

**`get_img_url` variations**:
- Simple (identical): `top_stories.py`, `videos.py`, `view_more_news.py` - only checks `data-src`
- Complex: `images.py` - fallback chain for multiple attributes

### 3. Import Style Inconsistency

Two styles in use:
```python
# Style 1: Namespace import
from .. import webutils
webutils.get_text(...)

# Style 2: Direct import
from ..webutils import get_text, get_link
get_text(...)
```

### 4. Missing Type Hints

Most parsers lack type annotations on parameters and return types.

### 5. Inconsistent Error Handling

- `videos.py`, `top_stories.py`: Return `{'error': 'No subcomponents found'}`
- Others: Return empty list or partial data
- `Component.run_parser()`: Wraps in try/except with traceback

### 6. Docstring Quality

- Some excellent: `general.py`, `videos.py`, `knowledge.py`
- Some minimal: `shopping_ads.py`, `scholarly_articles.py`
- Some missing: helper functions

---

## Key Insight: BaseResult Handles Everything

Research into `components.py` reveals that **all parser output goes through BaseResult validation**:

```python
def add_parsed_result(self, parsed_result):
    parsed_result_validated = BaseResult(**parsed_result).model_dump()
    self.result_list.append(parsed_result_validated)
```

This means:
- **Missing fields** → automatically filled with defaults (`None` or `0`)
- **Extra fields** → silently dropped (standard Pydantic behavior)
- **Type validation** → Pydantic enforces schema

**Implication**: Parsers can return minimal dicts with only populated fields. The PARSED template pattern in `ads.py` is redundant boilerplate - 96% of parsers don't use it and work fine.

---

## Notable Parser Patterns

### `ads.py` - Well-Structured (but template unnecessary)

Good aspects worth keeping:
1. **Changelog** in module docstring tracks evolution
2. **Type hints** on function signatures
3. **Classify-then-dispatch** pattern for handling variants
4. **Internal parser registry** for carousel variations
5. **Uses `webutils`** consistently via namespace import
6. **Sub-parsers** for distinct sub-types (carousel, standard, legacy)

The `PARSED` template constant can be removed - it adds boilerplate without benefit.

---

## Proposed Standard Structure

### 1. Module Template

```python
"""Parser for {component_type} components

Changelog
---------
YYYY-MM-DD: Description of change
"""

from .. import webutils
import bs4


def parse_{component_type}(cmpt: bs4.element.Tag) -> list[dict]:
    """Parse a {component_type} component.

    Args:
        cmpt: BeautifulSoup Tag containing the component HTML

    Returns:
        List of parsed result dictionaries conforming to BaseResult
    """
    subs = _find_subcomponents(cmpt)
    if not subs:
        return [{'type': '{component_type}', 'sub_rank': 0, 'error': 'No subcomponents found'}]

    return [_parse_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]


def _find_subcomponents(cmpt: bs4.element.Tag) -> list[bs4.element.Tag]:
    """Find subcomponent elements within the component."""
    # Try multiple selectors in order of preference
    selectors = [
        {'name': 'div', 'attrs': {'class': 'primary-class'}},
        {'name': 'div', 'attrs': {'class': 'fallback-class'}},
    ]
    for kwargs in selectors:
        subs = webutils.find_all_divs(cmpt, **kwargs)
        if subs:
            return subs
    return []


def _parse_sub(sub: bs4.element.Tag, sub_rank: int = 0) -> dict:
    """Parse a single subcomponent."""
    # Return only populated fields - BaseResult fills defaults
    return {
        'type': '{component_type}',
        'sub_rank': sub_rank,
        'title': webutils.get_text(sub, 'h3'),
        'url': webutils.get_link(sub),
        'text': webutils.get_text(sub, 'div', {'class': 'text-class'}),
        'cite': webutils.get_text(sub, 'cite'),
    }
```

**Note**: No PARSED_TEMPLATE needed - BaseResult handles defaults for missing fields.

### 2. Shared Utilities to Add to `webutils.py`

Only `get_img_url` (simple version) should be consolidated. `parse_alink` variations are intentionally different.

```python
def get_img_url(soup: BeautifulSoup | Tag, attr: str = 'data-src') -> str | None:
    """Extract image URL from img tag.

    Args:
        soup: BeautifulSoup element containing an img tag
        attr: Attribute to extract URL from (default: 'data-src')

    Returns:
        Image URL or None if not found
    """
    img = soup.find('img')
    if img and attr in img.attrs:
        return img.attrs[attr]
    return None
```

**Note**: Keep `images.py` version separate - it needs a fallback chain for multiple attributes.

### 3. Extra Fields - Current Status

These parsers extract fields that BaseResult silently drops:

| Parser | Dropped Fields | Notes |
|--------|----------------|-------|
| `view_more_news.py` | `timestamp`, `img_url` | News article metadata |
| `news_quotes.py` | `timestamp` | Quote timestamp |
| `twitter_result.py` | `timestamp` | Tweet timestamp |
| `knowledge_rhs.py` | `rhs_column` | Layout indicator |
| `ads.py` | `visible` | Filtered before return (intentional) |

**Decision**: Keep dropping these for now - they aren't used downstream. If needed later, move to `details` dict:

```python
# Future option if these fields become needed:
parsed['details'] = {
    'timestamp': webutils.get_text(sub, 'span', {'class': 'timestamp'}),
    'img_url': webutils.get_img_url(sub),
}
```

---

## Migration Strategy

### Phase 1: Preparation (Low Risk)

1. **Add shared utilities to `webutils.py`**
   - `parse_alink()`
   - `get_img_url()`
   - Add tests for new functions

2. **Run existing tests** to establish baseline

### Phase 2: Standardize Imports (Low Risk)

1. **Standardize on namespace import**: `from .. import webutils`
   - More explicit, avoids shadowing
   - Easier to grep for usage

### Phase 3: Refactor Individual Parsers (Medium Risk)

Refactor one parser at a time, ordered by complexity (simplest first):

| Priority | Parser | Complexity | Notes |
|----------|--------|------------|-------|
| 1 | `map_results.py` | Simple | Single result, no subs |
| 2 | `shopping_ads.py` | Simple | Basic structure |
| 3 | `scholarly_articles.py` | Simple | Basic structure |
| 4 | `searches_related.py` | Simple | Single result |
| 5 | `people_also_ask.py` | Simple | Single result |
| 6 | `available_on.py` | Simple | Single result with details |
| 7 | `banner.py` | Medium | Header + suggestions |
| 8 | `discussions_and_forums.py` | Medium | Good structure already |
| 9 | `twitter_result.py` | Medium | Has timestamp field |
| 10 | `twitter_cards.py` | Medium | Header + cards |
| 11 | `top_stories.py` | Medium | Multiple div patterns |
| 12 | `videos.py` | Medium | Multiple div patterns |
| 13 | `images.py` | Medium | Multiple sub-types |
| 14 | `view_more_news.py` | Medium | Has timestamp/img_url |
| 15 | `news_quotes.py` | Medium | Complex child parsing |
| 16 | `local_results.py` | Complex | Detailed parsing |
| 17 | `general.py` | Complex | Many sub-types, ratings |
| 18 | `knowledge.py` | Complex | Many sub-types |
| 19 | `knowledge_rhs.py` | Complex | Multiple results |
| 20 | `ads.py` | Already good | Just add type hints |
| 21 | `notices.py` | Already good | Class-based, keep as-is |

**For each parser**:
1. Update imports to namespace style
2. Replace duplicated functions with webutils calls
3. Add type hints
4. Remove PARSED template if present (ads.py)
5. Run full test suite

### Phase 4: Documentation (Low Risk)

1. Add changelog to parser modules lacking them
2. Ensure all public functions have docstrings
3. Document migration in project CHANGELOG.md

---

## Risk Mitigation

### Snapshot Testing

The project uses `syrupy` for snapshot testing. After each change:

```bash
# Run tests with verbose diff
pytest -vv

# If changes are intentional, update snapshots
pytest --snapshot-update
```

### Incremental Changes

- One parser per PR
- Full test suite between each change
- Easy to revert if issues arise

### Backward Compatibility

- Output schema enforced by `BaseResult` Pydantic model
- Any extra fields already being silently dropped
- Moving fields to `details` is the only breaking change (for external consumers accessing raw parser output)

---

## Decisions Made

1. **Extra fields policy**: Keep dropping `timestamp`, `img_url`, etc. for now
   - Document which parsers use them (see "Extra Fields - Current Status" above)
   - Can move to `details` later if needed

2. **PARSED template**: Remove from `ads.py` - unnecessary boilerplate
   - BaseResult handles all defaults

3. **Class-based vs functional**: Keep class-based where it adds clarity
   - `notices.py` stays class-based (complex sub-type logic)

4. **Import style**: Use namespace imports (`from .. import webutils`)
   - More explicit, avoids shadowing

5. **Delegation parsers**: Keep `perspectives.py`, `latest_from.py`, etc. as thin wrappers
   - They provide clear type distinction

---

## Implementation Checklist

### Phase 1: webutils.py
- [ ] Add `get_img_url()` to webutils.py (simple version only)
- [ ] Add tests for new webutils function

### Phase 2: Remove Duplicates
- [ ] `knowledge.py` - rename local `get_text()` to `_join_text()` to avoid shadowing
- [ ] `videos.py` - replace local `get_img_url()` with webutils version
- [ ] `top_stories.py` - replace local `get_img_url()` with webutils version
- [ ] `view_more_news.py` - replace local `get_img_url()` with webutils version

**Keep as-is** (component-specific behavior):
- `parse_alink()` in all 4 files - intentionally different
- `get_img_url()` in `images.py` - needs fallback chain

### Phase 3: Standardize
- [ ] Update imports to namespace style across all parsers
- [ ] Add type hints to parser functions
- [ ] Remove PARSED template from `ads.py`

### Phase 4: Documentation
- [ ] Add changelogs to parser modules lacking them
- [ ] Document migration in project CHANGELOG.md

## Related Documentation

- `component-parser-details-field.md` - Documents `details` field usage in each parser
