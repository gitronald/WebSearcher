---
status: done
branch: dev
created: 2026-02-22T12:56:12-08:00
completed: 2026-02-06T10:18:38-08:00
pr: https://github.com/gitronald/WebSearcher/pull/94
---

# Formalize multi-selector text extraction with `get_text_by_selectors`

## Context

Eight component parsers independently implement the same "try multiple CSS selectors, return first non-null text" pattern using `get_text()`. Each uses a slightly different idiom (`next()` generator, list comprehension + filter, `for` loop with `break`, inline list + index).

All reduce to the same logic: iterate `(tag_name, attrs)` pairs via `get_text()`, return first match.

`webutils.py` already has `get_text`, `get_div`, `get_link`, and `get_link_list` but nothing for multi-selector fallback. Adding `get_text_by_selectors` there formalizes the pattern.

### Instances covered

| # | File | Function/location | Field | Selectors |
|---|------|-------------------|-------|-----------|
| 1 | `top_stories.py:52` | `get_title()` | title | `div.n0jPhd`, `div.eAaXgc` |
| 2 | `discussions_and_forums.py:29` | `get_title()` | title | `div.zNWc4c`, `div.qyp6xb` |
| 3 | `discussions_and_forums.py:36` | `get_cite()` | cite | `div.LbKnXb`, `div.VZGVuc` |
| 4 | `map_results.py:21` | `get_title()` | title | `div.aiAXrc` |
| 5 | `people_also_ask.py:35` | `parse_question()` | title | 5 div classes (`rc`, `yuRUbf`, `iDjcJe`, `JlqpRe`, `cbphWd`) |
| 6 | `local_results.py:22` | inline in `parse_local_results()` | header | `h2[role=heading]`, `div[aria-level=2, role=heading]` |
| 7 | `searches_related.py:12` | inline in `parse_searches_related()` | header | `h2[role=heading]`, `div[aria-level=2, role=heading]` |
| 8 | `ads.py:153` | `_parse_ad_standard_text()` | text | `div.yDYNvb`, `div.Va3FIb` |

### Out of scope

These use the same "try multiple, take first" structure but with `get_link()`, `find()`, or mixed extraction — different base function, different abstraction:
- `discussions_and_forums.py:22` — `get_url()` uses `get_link()`
- `ads.py:121` — `_parse_ad_secondary_sub_details()` uses `find()`/`get_link_list()`
- `general.py:61-62` — `or` chain returning elements, not text
- `images.py:48` — mixed `get_text` + `get_img_alt`
- `top_stories.py:61` — `get_cite()` — complex if/elif with image alt extraction

## Plan

### 1. Add `get_text_by_selectors()` to `webutils.py`

Add after `get_link_list()` (line 162), before `find_all_divs`. Follows the existing utility style. Supports the `strip` parameter needed by `people_also_ask.py`:

```python
def get_text_by_selectors(
    soup: Tag | None,
    selectors: list[tuple[str, Mapping[str, Any]]] | None = None,
    strip: bool = False,
) -> str | None:
    """Get text by trying multiple selectors, return first non-null"""
    if not soup or not selectors:
        return None
    for name, attrs in selectors:
        text = get_text(soup, name, attrs, strip=strip)
        if text:
            return text
    return None
```

No new imports needed — `Tag`, `Mapping`, `Any`, and `get_text` are already in scope.

### 2. Update `top_stories.py`

This file uses direct imports (`from ..webutils import ...`).

**Line 1** — add `get_text_by_selectors` to import:
```python
# before
from ..webutils import find_all_divs, find_children, get_text, get_link

# after
from ..webutils import find_all_divs, find_children, get_text, get_text_by_selectors, get_link
```

**After imports** — add module-level constant:
```python
TITLE_SELECTORS = [
    ('div', {'class': 'n0jPhd'}),   # Top Stories
    ('div', {'class': 'eAaXgc'}),   # Perspectives
]
```

**Line 44** — update call in `parse_top_story()`:
```python
# before
'title': get_title(sub),

# after
'title': get_text_by_selectors(sub, TITLE_SELECTORS),
```

**Lines 52-58** — delete the local `get_title()` function.

### 3. Update `discussions_and_forums.py`

This file uses module-level import (`from .. import webutils`). No import change needed.

**After imports** — add module-level constants:
```python
TITLE_SELECTORS = [
    ('div', {'class': 'zNWc4c'}),
    ('div', {'class': 'qyp6xb'}),
]

CITE_SELECTORS = [
    ('div', {'class': 'LbKnXb'}),
    ('div', {'class': 'VZGVuc'}),
]
```

**Line 17** — update title call:
```python
# before
"title": get_title(cmpt),

# after
"title": webutils.get_text_by_selectors(cmpt, TITLE_SELECTORS),
```

**Line 19** — update cite call:
```python
# before
"cite": get_cite(cmpt)

# after
"cite": webutils.get_text_by_selectors(cmpt, CITE_SELECTORS),
```

**Lines 29-34** — delete local `get_title()`.

**Lines 36-41** — delete local `get_cite()`.

### 4. Update `map_results.py`

Uses module-level import. No import change needed.

**After imports** — add module-level constant:
```python
TITLE_SELECTORS = [
    ('div', {'class': 'aiAXrc'}),
]
```

**Line 18** — update call:
```python
# before
'title': get_title(cmpt)

# after
'title': webutils.get_text_by_selectors(cmpt, TITLE_SELECTORS)
```

**Lines 21-23** — delete local `get_title()` (including commented-out line).

### 5. Update `people_also_ask.py`

Uses module-level import. No import change needed.

**After imports** — add module-level constant:
```python
QUESTION_SELECTORS = [
    ('div', {'class': 'rc'}),
    ('div', {'class': 'yuRUbf'}),
    ('div', {'class': 'iDjcJe'}),    # 2023-01-01
    ('div', {'class': 'JlqpRe'}),    # 2023-11-16
    ('div', {'class': 'cbphWd'}),     # 2021-01-09
]
```

**Lines 32-49** — replace entire `parse_question()` body:
```python
# before
def parse_question(question):
    """Parse an individual question in a "People Also Ask" component"""

    title_divs = [
        question.find('div', {'class':'rc'}),
        question.find('div', {'class':'yuRUbf'}),
        question.find('div', {'class':'iDjcJe'}),  # 2023-01-01
        question.find('div', {'class':'JlqpRe'}),  # 2023-11-16
        question.find('div', {'class':'cbphWd'}),  # 2021-01-09
    ]

    # Return first valid text found
    for title_div in filter(None, title_divs):
        text = webutils.get_text(title_div, strip=True)
        if text:
            return text

    return None

# after
def parse_question(question):
    """Parse an individual question in a "People Also Ask" component"""
    return webutils.get_text_by_selectors(question, QUESTION_SELECTORS, strip=True)
```

### 6. Update `local_results.py`

Uses module-level import. No import change needed.

**After imports** — add module-level constant:
```python
HEADER_SELECTORS = [
    ("h2", {"role": "heading"}),
    ("div", {"aria-level": "2", "role": "heading"}),
]
```

**Lines 21-28** — replace inline header extraction:
```python
# before
        # Set first non-empty header as sub_type (e.g. "Places" -> places)
        header_list = [
            webutils.get_text(cmpt, "h2", {"role":"heading"}),
            webutils.get_text(cmpt, 'div', {'aria-level':"2", "role":"heading"}),
        ]
        header_list = list(filter(None, header_list))
        if header_list:
            sub_type = str(header_list[0]).lower().replace(" ", "_")

# after
        # Set first non-empty header as sub_type (e.g. "Places" -> places)
        header = webutils.get_text_by_selectors(cmpt, HEADER_SELECTORS)
        if header:
            sub_type = header.lower().replace(" ", "_")
```

### 7. Update `searches_related.py`

Uses module-level import. No import change needed.

**After imports** — add module-level constant:
```python
HEADER_SELECTORS = [
    ("h2", {"role": "heading"}),
    ("div", {"aria-level": "2", "role": "heading"}),
]
```

**Lines 11-17** — replace inline header extraction:
```python
# before
    # Set first non-empty header as sub_type (e.g. "Additional searches" -> additional_searches)
    header_list = [
        webutils.get_text(cmpt, "h2", {"role":"heading"}),
        webutils.get_text(cmpt, 'div', {'aria-level':"2", "role":"heading"}),
    ]
    header_list = list(filter(None, header_list))
    parsed['sub_type'] = str(header_list[0]).lower().replace(" ", "_") if header_list else None

# after
    # Set first non-empty header as sub_type (e.g. "Additional searches" -> additional_searches)
    header = webutils.get_text_by_selectors(cmpt, HEADER_SELECTORS)
    parsed['sub_type'] = header.lower().replace(" ", "_") if header else None
```

### 8. Update `ads.py`

Uses module-level import. No import change needed.

**After existing `SUB_TYPES` constant (line 24)** — add module-level constant:
```python
AD_STANDARD_TEXT_SELECTORS = [
    ('div', {'class': 'yDYNvb'}),
    ('div', {'class': 'Va3FIb'}),
]
```

**Lines 153-163** — simplify `_parse_ad_standard_text()`:
```python
# before
        def _parse_ad_standard_text(sub: bs4.element.Tag) -> str:
            name_attrs = [
                {'name': 'div', 'attrs': {'class': 'yDYNvb'}},
                {'name': 'div', 'attrs': {'class': 'Va3FIb'}},
            ]
            for kwargs in name_attrs:
                text = webutils.get_text(sub, **kwargs)
                if text:
                    break
            label = webutils.get_text(sub, 'span', {'class': 'mXsQRe'})
            return f"{text} <label>{label}</label>" if label else text

# after
        def _parse_ad_standard_text(sub: bs4.element.Tag) -> str:
            text = webutils.get_text_by_selectors(sub, AD_STANDARD_TEXT_SELECTORS)
            label = webutils.get_text(sub, 'span', {'class': 'mXsQRe'})
            return f"{text} <label>{label}</label>" if label else text
```

## Files to modify

| File | Changes |
|------|---------|
| `WebSearcher/webutils.py` | Add `get_text_by_selectors()` after line 162 |
| `WebSearcher/component_parsers/top_stories.py` | Add import + `TITLE_SELECTORS`, update call, delete local `get_title()` |
| `WebSearcher/component_parsers/discussions_and_forums.py` | Add `TITLE_SELECTORS` + `CITE_SELECTORS`, update calls, delete local `get_title()` + `get_cite()` |
| `WebSearcher/component_parsers/map_results.py` | Add `TITLE_SELECTORS`, update call, delete local `get_title()` |
| `WebSearcher/component_parsers/people_also_ask.py` | Add `QUESTION_SELECTORS`, replace `parse_question()` body |
| `WebSearcher/component_parsers/local_results.py` | Add `HEADER_SELECTORS`, replace inline header extraction |
| `WebSearcher/component_parsers/searches_related.py` | Add `HEADER_SELECTORS`, replace inline header extraction |
| `WebSearcher/component_parsers/ads.py` | Add `AD_STANDARD_TEXT_SELECTORS`, simplify `_parse_ad_standard_text()` |

No changes needed to `component_parsers/__init__.py`.

Delegating parsers (`perspectives.py`, `recent_posts.py`, `latest_from.py`, `local_news.py`) require no changes — they call `parse_top_stories()` which uses the updated code path.

## Verification

1. **Unit tests** — all snapshot and structural tests pass:
   ```bash
   poetry run pytest tests/ -q
   ```

2. **Reparse saved SERPs** — confirm identical output on demo datasets:
   ```bash
   poetry run python -c "
   import json, WebSearcher as ws
   for version in ['v0.6.7a2', 'v0.6.7a3']:
       fp = f'data/demo-ws-{version}/serps.json'
       with open(fp) as f:
           serps = [json.loads(line) for line in f]
       for serp in serps:
           results = ws.parse_serp(serp['html'])
       print(f'{version}: {len(serps)} serps parsed ok')
   "
   ```

3. **Targeted check** — verify affected component types still produce correct values:
   ```bash
   poetry run python -c "
   import json, WebSearcher as ws
   target_types = {
       'top_stories', 'perspectives', 'recent_posts', 'latest_from', 'local_news',
       'discussions_and_forums', 'map_results', 'people_also_ask',
       'local_results', 'searches_related', 'ad',
   }
   for version in ['v0.6.7a2', 'v0.6.7a3']:
       fp = f'data/demo-ws-{version}/serps.json'
       with open(fp) as f:
           serps = [json.loads(line) for line in f]
       for serp in serps:
           for r in ws.parse_serp(serp['html']):
               if r['type'] in target_types:
                   title = str(r.get('title') or '')[:50]
                   print(f\"{version} | {r['type']:30s} | {title}\")
   "
   ```
