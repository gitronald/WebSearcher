---
status: done
branch: dev
created: 2026-02-22T12:56:12-08:00
completed: 2026-03-15T16:23:47-07:00
pr: https://github.com/gitronald/WebSearcher/pull/100
---

# Component Parser Details Field Documentation

## Overview

This document catalogs how each component parser uses the `details` field and documents the `parse_alink`/`get_img_url` helper function variations.

---

## Parsers Using `details` Field

### 1. `general.py`

**Usage**: Complex dict with multiple possible structures depending on `sub_type`

| sub_type | details structure |
|----------|-------------------|
| `submenu_rating` | `{rating: float, reviews: int}` |
| `submenu` | `{links: [{text, url}, ...]}` |
| `submenu_mini` | `{links: [{text, url}, ...]}` |
| `submenu_scholarly` | `{links: [{text, url}, ...]}` |
| `submenu_product` | `{price: str, stock: str}` |
| (general video) | `{source: str, duration: str}` |

**Notes**: Most complex usage. Uses `parse_alink_list()` for links.

---

### 2. `ads.py`

**Usage**: `DetailsList.to_dicts()` — all output is `list[dict]` with full DetailsItem keys `{url, title, text, misc}`, but different fields are populated per variant.

| sub_type | details structure | Fields populated |
|----------|-------------------|-----------------|
| `submenu` | `[{url, title, text, misc}, ...]` | url + title + text |
| `secondary` | `[{url, title, text, misc}, ...]` | url only |
| `legacy` | `[{url, title, text, misc}, ...]` | text only |
| `local_service` | `[{url, title, text, misc}, ...]` | text only |
| `carousel_*` | `None` | n/a |

**Notes**: All variants use `DetailsList.to_dicts()` except carousel (no details).

---

### 3. `knowledge.py`

**Usage**: Complex dict with heading, URLs, text, and image

```python
details = {
    'heading': str | None,
    'urls': [{'url': str, 'text': str}, ...],
    'text': str | None,  # for certain sub_types
    'img_url': str | None
}
```

**Notes**: Always includes `heading` and `urls`. `text` added for specific sub_types (featured_snippet, dictionary, translate, election, panel).

---

### 4. `knowledge_rhs.py`

**Usage**: Dict with optional keys

```python
# Main panel
details = {
    'img_urls': [url, ...],      # optional
    'subtitle': str,              # optional
    'urls': [{'url', 'text'}, ...] # optional
}

# Subcomponents
details = [{'url', 'text'}, ...]  # list of links
```

**Notes**: Main panel uses dict, subcomponents use list. Falls back to `None` if empty.

---

### 5. `local_results.py`

**Usage**: Dict with location metadata

```python
details = {
    'rating': float,
    'n_reviews': int,
    'loc_label': str,       # e.g., "Restaurant"
    'contact': str,
    # Plus dynamic link keys:
    'website': url,
    'directions': url,
    'menu': url,
    # etc.
}
```

**Notes**: Link keys are dynamic based on what's available (website, directions, menu, etc.)

---

### 6. `available_on.py`

**Usage**: `DetailsList.to_dicts()` — full DetailsItem keys with cost in `misc`

```python
details = [
    {'url': str, 'title': str, 'text': '', 'misc': {'cost': str}},
    ...
]
```

**Example**: `[{'url': '...', 'title': 'Netflix', 'text': '', 'misc': {'cost': '$9.99/mo'}}]`

---

### 7. `searches_related.py`

**Usage**: List of related search strings

```python
details = ['related query 1', 'related query 2', ...]
```

**Notes**: Same content as `text` field (which joins with `<|>`), but as a list.

---

### 8. `people_also_ask.py`

**Usage**: List of question strings

```python
details = ['Question 1?', 'Question 2?', ...]
```

**Notes**: Same content as `text` field (which joins with `<|>`), but as a list.

---

### 9. `general_questions.py`

**Usage**: Copies `details` from `people_also_ask` result

```python
# Combines general result with PAA questions
parsed_list_general[0]['details'] = parsed_list_ppa[0].get('details', None)
```

---

### 10. `twitter_result.py`

**Usage**: Single URL string

```python
details = 'https://twitter.com/...'  # URL to the specific tweet
```

**Notes**: Unusual - stores a single URL string, not a dict or list.

---

### 11. `top_image_carousel.py`

**Usage**: List of link dicts

```python
details = [
    {'text': str, 'url': str},
    ...
]
```

**Notes**: Parses carousel links using local `parse_alink()`.

---

### 12. `footer.py` (img_cards)

**Usage**: `DetailsList.to_dicts()` — full DetailsItem keys

```python
details = [
    {'url': str, 'title': '', 'text': str, 'misc': {}},  # url=img src, text=alt text
    ...
]
```

---

### 13. `shopping_ads.py` (sponsored hotels)

**Usage**: Dict with location-like metadata. Only the `_parse_sponsored_hotel` variant populates details; standard product listing ads (`_parse_pla_unit`) do not.

```python
details = {
    'price': str,
    'source': str,
    'rating': str,
    'reviews': str,       # e.g. "(345)", "(2.1K)"
    'stars': str,         # optional
    'amenity': str,       # optional
}
```

**Notes**: Keys are conditionally added — only present if parsed from HTML. Standard `_parse_pla_unit` does not use details.

---

## Parsers NOT Using `details`

These parsers don't populate the `details` field (BaseResult defaults to `None`):

- `banner.py`
- `discussions_and_forums.py`
- `images.py`
- `latest_from.py` (delegates to top_stories)
- `local_news.py` (delegates to top_stories)
- `map_results.py`
- `news_quotes.py`
- `notices.py`
- `perspectives.py` (delegates to top_stories)
- `recent_posts.py` (delegates to top_stories)
- `scholarly_articles.py`
- `top_stories.py`
- `twitter_cards.py`
- `videos.py` (has commented-out details code)
- `view_more_news.py`

---

## `parse_alink` Variations

**NOT identical** - each has component-specific behavior:

| File | Text extraction | URL extraction | Notes |
|------|-----------------|----------------|-------|
| `general.py` | `a.text` | `a.attrs['href']` | Requires href |
| `knowledge.py` | `a.get_text('|')` | `a['href']` | Uses `|` separator |
| `knowledge_rhs.py` | `a.text` | `a['href']` | Simplest |
| `top_image_carousel.py` | `a.get_text('|')` | `href` OR `data-url` | Most flexible |

**Recommendation**: Keep separate - they're intentionally different for their component contexts.

---

## `get_img_url` Variations

**Two distinct patterns**:

### Simple version (identical in 3 files)
```python
# top_stories.py, videos.py, view_more_news.py
def get_img_url(soup):
    img = soup.find('img')
    if img and 'data-src' in img.attrs:
        return img.attrs['data-src']
```

### Complex version (images.py only)
```python
# Tries multiple sources with fallback chain:
# 1. img src (if not data URL)
# 2. data-lpage attribute
# 3. img title attribute
```

**Recommendation**: Could consolidate the 3 identical simple versions to `webutils.py`. Keep `images.py` version separate (needs fallback chain for image-heavy parsing).

---

## Summary Table

| Parser | Current type | Target type | Content |
|--------|-------------|-------------|---------|
| `general.py` (rating) | `dict` | `"review"` | rating, reviews |
| `general.py` (submenu) | `dict` | `"hyperlinks"` | links list |
| `general.py` (product) | `dict` | `"product"` | price, stock |
| `general.py` (video) | `dict` | `"video"` | source, duration |
| `ads.py` (menu) | `list[dict]` | `"menu"` | url + title + text items |
| `ads.py` (sitelinks) | `list[dict]` | `"links"` | url-only items |
| `ads.py` (legacy/local_service) | `list[dict]` | `"text"` | text-only items |
| `knowledge.py` | `dict` | `"panel"` | heading, urls, text, img_url |
| `knowledge_rhs.py` main | `dict` | `"panel"` | img_urls, subtitle, urls |
| `knowledge_rhs.py` subs | `list[dict]` | `"hyperlinks"` | url + text items |
| `local_results.py` | `dict` | `"ratings"` | rating, reviews, contact, links |
| `shopping_ads.py` (hotels) | `dict` | `"ratings"` | price, source, rating, reviews |
| `available_on.py` | `list[dict]` | `"providers"` | title, url, cost items |
| `searches_related.py` | `list[str]` | `"text"` | query strings |
| `people_also_ask.py` | `list[str]` | `"text"` | question strings |
| `general_questions.py` | `list[str]` | `"text"` | copied from PAA |
| `twitter_result.py` | `str` | `"tweet"` | single tweet URL |
| `top_image_carousel.py` | `list[dict]` | `"hyperlinks"` | url + text items |
| `footer.py` | `list[dict]` | `"hyperlinks"` | url + text items |

---

## Log

### 2026-03-15: Consolidation toward `dict | None`

Plan 017 (standardize data models) identified `details: Any | None` as a problem. The goal is to make `details` always `dict | None` — dicts can contain lists and nested structures, but the top-level type should be consistent. This enables typed detail models later (plan 017 Phase 4).

#### Current state by type

**Already `dict` (needs `type` key added):**
- `general.py` — various shapes by sub_type (rating/reviews, links, price/stock, source/duration)
- `knowledge.py` — `{heading, urls, text, img_url}`
- `knowledge_rhs.py` main — `{img_urls, subtitle, urls}`
- `local_results.py` — `{rating, n_reviews, loc_label, contact, ...links}`
- `shopping_ads.py` (hotels) — `{price, source, rating, reviews, stars, amenity}`

**Currently `list[dict]` (from `DetailsList.to_dicts()`):**
- `ads.py` — menu items, sitelinks, bottom text
- `knowledge_rhs.py` subs — `[{url, text}, ...]`
- `available_on.py` — `[{title, cost, url}, ...]` (via DetailsItem with misc)
- `top_image_carousel.py` — `[{text, url}, ...]`
- `footer.py` img_cards — `[{text, url}, ...]`

**Currently `list[str]`:**
- `searches_related.py` — `['query 1', 'query 2', ...]`
- `people_also_ask.py` — `['Question 1?', 'Question 2?', ...]`
- `general_questions.py` — copies details from PAA

**Currently `str`:**
- `twitter_result.py` — single tweet URL

#### What changes

Each non-dict case wraps its content under a key, and every details dict gets a `type` key so it's self-describing (consumers don't need to check the parent result's `sub_type` to interpret details). Types are consistent across parsers — if the structure is the same, the type is the same.

#### List item types

Based on DetailsItem fields populated:

| details.type | Structure | Fields used |
|-------------|-----------|-------------|
| `"text"` | `{type, items: [str, ...]}` | text only (strings, not DetailsItem) |
| `"links"` | `{type, items: [{url}, ...]}` | url only |
| `"hyperlinks"` | `{type, items: [{url, text}, ...]}` | url + text |
| `"menu"` | `{type, items: [{url, text, title}, ...]}` | url + text + title |

#### Metadata types

Unique structures per parser, not list-based:

| details.type | Keys |
|-------------|------|
| `"review"` | rating, reviews |
| `"product"` | price, stock |
| `"video"` | source, duration |
| `"ratings"` | rating, n_reviews, loc_label, contact, ...links |
| `"panel"` | heading, urls, text, img_url |
| `"providers"` | items (each with title, url, cost) |
| `"tweet"` | url |

#### Changes for non-dict cases

| Parser | details.type | Before | After |
|--------|-------------|--------|-------|
| `ads.py` (menu) | `"menu"` | `[{url, title, text}, ...]` | `{"type": "menu", "items": [...]}` |
| `ads.py` (sitelinks) | `"links"` | `[{url}, ...]` | `{"type": "links", "items": [...]}` |
| `ads.py` (legacy bottom) | `"text"` | `[{text}, ...]` | `{"type": "text", "items": [...]}` |
| `ads.py` (local_service rating) | `"text"` | `[{text}, ...]` | `{"type": "text", "items": [...]}` |
| `knowledge_rhs.py` subs | `"hyperlinks"` | `[{url, text}, ...]` | `{"type": "hyperlinks", "items": [...]}` |
| `available_on.py` | `"providers"` | `[{title, url, misc: {cost}}, ...]` | `{"type": "providers", "items": [...]}` |
| `top_image_carousel.py` | `"hyperlinks"` | `[{url, text}, ...]` | `{"type": "hyperlinks", "items": [...]}` |
| `footer.py` | `"hyperlinks"` | `[{url, text}, ...]` | `{"type": "hyperlinks", "items": [...]}` |
| `searches_related.py` | `"text"` | `['query', ...]` | `{"type": "text", "items": [...]}` |
| `people_also_ask.py` | `"text"` | `['question', ...]` | `{"type": "text", "items": [...]}` |
| `twitter_result.py` | `"tweet"` | `'https://...'` | `{"type": "tweet", "url": "..."}` |

#### Changes for existing dict cases

| Parser | details.type | Existing keys (kept) |
|--------|-------------|---------------|
| `general.py` (rating) | `"review"` | rating, reviews |
| `general.py` (submenu/mini/scholarly) | `"hyperlinks"` | items (rename from links) |
| `general.py` (product) | `"product"` | price, stock |
| `general.py` (video) | `"video"` | source, duration |
| `knowledge.py` | `"panel"` | heading, urls, text, img_url |
| `knowledge_rhs.py` main | `"panel"` | img_urls, subtitle, urls |
| `local_results.py` | `"ratings"` | rating, n_reviews, loc_label, contact, ...links |
| `shopping_ads.py` (hotels) | `"ratings"` | price, source, rating, reviews, stars, amenity |

The parent result's `type` + `sub_type` already disambiguates in most cases, but `details.type` makes the dict self-describing. This also enables a discriminated union on `details.type` later (plan 017 Phase 4).

#### Notes

- This is a breaking change for downstream consumers of the `details` field
- `general_questions.py` doesn't need its own change — it copies from PAA
- Snapshot tests will need updating after this change
- The `DetailsList.to_dicts()` callers are the bulk of the work; wrapping in a dict at the call site is mechanical
- After consolidation, `BaseResult.details` can be tightened from `Any | None` to `dict | None`
