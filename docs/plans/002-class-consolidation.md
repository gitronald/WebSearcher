---
status: done
branch: dev
created: 2026-02-22T12:56:12-08:00
completed: 2026-03-15T15:37:45-07:00
pr: https://github.com/gitronald/WebSearcher/pull/100
---

# Class Consolidation Plan: Models and Details Field

## Current Model Architecture

### Model Relationships

```
models/
├── __init__.py           # Empty (exports nothing)
├── configs.py            # Configuration classes
│   ├── BaseConfig        # Base with .create() factory
│   ├── LogConfig         # Logging settings
│   ├── SeleniumConfig    # Selenium driver settings
│   ├── RequestsConfig    # Requests session settings
│   ├── SearchMethod      # Enum: REQUESTS | SELENIUM
│   └── SearchConfig      # Composite config container
│
├── searches.py           # Search-related classes
│   └── SearchParams      # Query params with computed URL/serp_id
│       └── extends BaseConfig
│
├── data.py               # Core data classes
│   ├── BaseResult        # Single parsed result item
│   └── BaseSERP          # Complete SERP metadata
│
└── cmpt_mappings.py      # Type metadata (not Pydantic)
    ├── HEADER_RESULT_TYPES
    ├── MAIN_RESULT_TYPES
    ├── FOOTER_RESULT_TYPES
    └── ALL_RESULT_TYPES
```

### Data Flow Through Models

```
SearchParams          → SearchEngine executes search
     ↓
BaseSERP              → Raw HTML + metadata stored
     ↓
Extractor             → HTML parsed into ComponentList
     ↓
Component.parse()     → Results validated against BaseResult
     ↓
list[BaseResult]      → Final output (as dicts)
```

### Current BaseResult Structure

```python
class BaseResult(BaseModel):
    sub_rank: int = 0
    type: str = 'unclassified'
    sub_type: str | None = None
    title: str | None = None
    url: str | None = None
    text: str | None = None
    cite: str | None = None
    details: Any | None = None      # ← PROBLEM: Untyped
    error: str | None = None
```

---

## Problem: Untyped `details` Field

The `details` field currently accepts `Any`, resulting in:
- No type safety or validation
- No IDE autocomplete for consumers
- No documentation of expected structure
- Runtime errors when accessing nested fields

### Current Details Variations (from component-parser-details-field.md)

| Parser | Structure | Example |
|--------|-----------|---------|
| `general.py` | `dict` with rating/links/price | `{rating: 4.5, reviews: 100}` |
| `ads.py` | `list[dict]` or `list[str]` | `[{url, title, text}, ...]` |
| `knowledge.py` | `dict` with heading/urls/text/img | `{heading: str, urls: [...]}` |
| `knowledge_rhs.py` | `dict` or `list[dict]` | `{img_urls: [...], subtitle: str}` |
| `local_results.py` | `dict` with location metadata | `{rating: float, contact: str}` |
| `available_on.py` | `list[dict]` | `[{title, cost, url}, ...]` |
| `searches_related.py` | `list[str]` | `['query 1', 'query 2']` |
| `people_also_ask.py` | `list[str]` | `['Question 1?', ...]` |
| `twitter_result.py` | `str` | `'https://twitter.com/...'` |
| `top_image_carousel.py` | `list[dict]` | `[{text, url}, ...]` |
| `footer.py` | `list[dict]` | `[{text, url}, ...]` |

---

## Proposed Solution: Typed Details Models

### Option A: Discriminated Union (Recommended)

Use Pydantic's discriminated union with `type` as the discriminator:

```python
from pydantic import BaseModel, Field
from typing import Literal

# Base link structure used across multiple details types
class LinkItem(BaseModel):
    text: str | None = None
    url: str | None = None

# Specific details models by type
class GeneralRatingDetails(BaseModel):
    """Details for general results with ratings (sub_type: submenu_rating)"""
    rating: float | None = None
    reviews: int | None = None

class GeneralLinksDetails(BaseModel):
    """Details for general results with links (sub_type: submenu, submenu_mini, etc.)"""
    links: list[LinkItem] = Field(default_factory=list)

class GeneralProductDetails(BaseModel):
    """Details for general product results (sub_type: submenu_product)"""
    price: str | None = None
    stock: str | None = None

class GeneralVideoDetails(BaseModel):
    """Details for general video results"""
    source: str | None = None
    duration: str | None = None

class AdMenuDetails(BaseModel):
    """Details for ad submenu items"""
    items: list[LinkItem] = Field(default_factory=list)

class AdSecondaryDetails(BaseModel):
    """Details for secondary ad links"""
    urls: list[str] = Field(default_factory=list)

class KnowledgeDetails(BaseModel):
    """Details for knowledge panel results"""
    heading: str | None = None
    urls: list[LinkItem] = Field(default_factory=list)
    text: str | None = None
    img_url: str | None = None

class KnowledgeRhsDetails(BaseModel):
    """Details for right-hand-side knowledge panels"""
    img_urls: list[str] = Field(default_factory=list)
    subtitle: str | None = None
    urls: list[LinkItem] = Field(default_factory=list)

class LocalResultDetails(BaseModel):
    """Details for local business results"""
    rating: float | None = None
    n_reviews: int | None = None
    loc_label: str | None = None
    contact: str | None = None
    # Dynamic link fields stored as dict
    links: dict[str, str] = Field(default_factory=dict)

class StreamingOptionItem(BaseModel):
    title: str | None = None
    cost: str | None = None
    url: str | None = None

class AvailableOnDetails(BaseModel):
    """Details for streaming availability"""
    options: list[StreamingOptionItem] = Field(default_factory=list)

class QuestionsDetails(BaseModel):
    """Details for people_also_ask and searches_related"""
    items: list[str] = Field(default_factory=list)

class CarouselDetails(BaseModel):
    """Details for image carousels and card grids"""
    items: list[LinkItem] = Field(default_factory=list)

class TwitterResultDetails(BaseModel):
    """Details for Twitter results"""
    tweet_url: str | None = None

# Union type for all details
ResultDetails = (
    GeneralRatingDetails |
    GeneralLinksDetails |
    GeneralProductDetails |
    GeneralVideoDetails |
    AdMenuDetails |
    AdSecondaryDetails |
    KnowledgeDetails |
    KnowledgeRhsDetails |
    LocalResultDetails |
    AvailableOnDetails |
    QuestionsDetails |
    CarouselDetails |
    TwitterResultDetails |
    None
)
```

### Option B: TypedDict with Literal Discriminator

```python
from typing import TypedDict, Literal

class GeneralRatingDetails(TypedDict, total=False):
    detail_type: Literal['rating']
    rating: float
    reviews: int

class GeneralLinksDetails(TypedDict, total=False):
    detail_type: Literal['links']
    links: list[dict[str, str]]

# ... etc
```

### Option C: Keep `Any` but Add Validation Functions

Keep `details: Any` but add validation functions per type:

```python
def validate_general_details(details: Any, sub_type: str) -> bool:
    """Validate details structure for general results"""
    if sub_type == 'submenu_rating':
        return isinstance(details, dict) and 'rating' in details
    # ... etc
```

---

## Recommendation

**Option A (Discriminated Union)** provides:
- Full type safety with IDE support
- Automatic validation on parse
- Clear documentation of all structures
- Backward compatibility (existing dicts will validate)

### Implementation Steps

1. Create new file `models/details.py` with all detail models
2. Update `BaseResult.details` type to `ResultDetails`
3. Update each parser to construct the appropriate detail model
4. Add migration tests to ensure existing data validates

### Migration Strategy

Since parsers currently return plain dicts, the migration is incremental:
- Pydantic automatically coerces dicts to models
- Parsers can continue returning dicts (will be validated)
- Optionally update parsers to return model instances

---

## Additional Consolidation Opportunities

### 1. Export Models from `__init__.py`

```python
# models/__init__.py
from .data import BaseResult, BaseSERP
from .searches import SearchParams
from .configs import (
    BaseConfig, LogConfig, SeleniumConfig,
    RequestsConfig, SearchMethod, SearchConfig
)
from .details import ResultDetails, LinkItem  # New
```

### 2. Add Type Validation to cmpt_mappings.py

Link the details models to result types:

```python
from .details import (
    GeneralRatingDetails, KnowledgeDetails, # etc
)

MAIN_RESULT_TYPES = {
    "general": {
        "description": "Standard web search results",
        "sub_types": [...],
        "details_model": GeneralLinksDetails | GeneralRatingDetails,  # New
    },
    # ... etc
}
```

### 3. Component Class Type Hints

```python
# components.py
class Component:
    def __init__(
        self,
        elem: bs4.element.Tag,
        section: Literal["header", "main", "footer", "rhs"] = "unknown",
        type: str = "unknown",
        cmpt_rank: int | None = None
    ) -> None:
```

---

## File Changes Summary

| File | Changes |
|------|---------|
| `models/details.py` | **NEW** - All detail model classes |
| `models/data.py` | Update `BaseResult.details` type annotation |
| `models/__init__.py` | Add exports for new models |
| `models/cmpt_mappings.py` | Optionally link details models to types |
| `component_parsers/*.py` | Optionally update to return model instances |

---

## Open Questions

1. **Backward compatibility**: Should we keep accepting plain dicts via Pydantic coercion, or require model instances?
2. **Dynamic fields**: `local_results.py` has dynamic link keys (website, directions, menu). Use `dict[str, str]` or defined fields?
3. **Strict vs permissive**: Should unknown detail structures raise errors or pass through?
