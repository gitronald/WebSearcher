---
status: done
branch: parser-updates
created: 2026-02-22T12:56:12-08:00
completed: 2026-02-05T18:58:42-08:00
pr: https://github.com/gitronald/WebSearcher/pull/93
---

# Parser Updates (v0.6.7a2) — Completed

## Summary

Fixed 5 classification issues and 3 parser issues found in `data/demo-ws-v0.6.7a2/` demo data. All were broken (producing `unknown`, errors, or null fields), so every fix is a net improvement with no working behavior regressed.

## Issues & Fixes

### Fix 1: Tag-agnostic heading search (3 classifications fixed)

**Root cause:** Google changed heading tags from `<h2>`/`<div>` to `<span>` with `aria-level` and `role="heading"` attributes. `ClassifyHeaderText._classify_header()` had two `div`-specific lines that never matched `<span>` headings.

**Components fixed:**
- cmpt 1: `general` → `people_also_ask` (heading: "People also ask")
- cmpt 5: `unknown` → `perspectives` (heading: "What people are saying")
- cmpt 12: `general` → `searches_related` (heading: "People also search for")

**Change in `WebSearcher/classifiers/header_text.py:28-32`:**
Replaced two `div`-specific `aria-level` searches with one tag-agnostic search:
```python
# Before (two lines):
header_list.extend(cmpt.find_all("div", {"aria-level":f"{level}", "role":"heading"}))
header_list.extend(cmpt.find_all("div", {"aria-level":f"{level}", "class":"XmmGVd"}))

# After (one line):
header_list.extend(cmpt.find_all(attrs={"aria-level": f"{level}", "role": "heading"}))
```

### Fix 2: "What people are saying" mapping

**Root cause:** "What people are saying" was in the `knowledge` mapping but should be `perspectives`.

**Change in `WebSearcher/classifiers/header_text.py`:**
Moved from `knowledge` list (line 86) to `perspectives` list (line 104):
```python
"perspectives": ["Perspectives & opinions",
                  "Perspectives",
                  "What people are saying"],
```

### Fix 3: Perspectives title extraction

**Root cause:** `parse_top_story()` only looked for `div.n0jPhd` titles. Perspectives items use `div.eAaXgc`.

**Change in `WebSearcher/component_parsers/top_stories.py`:**
Added `get_title()` helper following the existing multi-selector pattern used by `get_cite()`:
```python
def get_title(sub):
    """Get title from a subcomponent; try multiple, take first non-null"""
    title_list = [
        get_text(sub, 'div', {'class': 'n0jPhd'}),   # Top Stories
        get_text(sub, 'div', {'class': 'eAaXgc'}),   # Perspectives
    ]
    return next((t for t in title_list if t), None)
```

### Fix 4: Video result misclassified as `discussions_and_forums`

**Root cause:** `ClassifyMain.discussions_and_forums()` matched any `div.IFnjPb[role=heading]` regardless of text content. Component 8's heading said "In this video", not "Discussions and forums".

**Change in `WebSearcher/classifiers/main.py:44-49`:**
Tightened classifier to check heading text:
```python
@staticmethod
def discussions_and_forums(cmpt: bs4.element.Tag) -> str:
    heading = cmpt.find("div", {"class": "IFnjPb", "role": "heading"})
    if heading and heading.get_text(strip=True).startswith("Discussions and forums"):
        return 'discussions_and_forums'
    return "unknown"
```

### Fix 5: General parser missing video subcomponents

**Root cause:** `parse_general_results()` searched for `div.g` subcomponents, found none in video results (which use `div.PmEWq`), and fell back to the entire wrapper — losing the video-specific parsing path.

**Change in `WebSearcher/component_parsers/general.py`:**
Extracted subcomponent discovery into `find_subcomponents()` with video format support:
```python
def parse_general_results(cmpt) -> list:
    subs = find_subcomponents(cmpt)
    return [parse_general_result(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

def find_subcomponents(cmpt) -> list:
    """Find subcomponents within a general component, trying known formats"""
    # Standard format
    subs = cmpt.find_all('div', {'class': 'g'})
    if subs:
        parent_g = cmpt.find('div', {'class': 'g'})
        if parent_g and parent_g.find_all('div', {'class': 'g'}):
            return [parent_g]  # Nested .g dedup
        return subs
    # Sub-results format (2023+)
    additional = cmpt.find_all('div', {'class': 'd4rhi'})
    if additional:
        return [cmpt.find('div')] + additional
    # Video results
    subs = cmpt.find_all('div', {'class': 'PmEWq'})
    if subs:
        return subs
    # Fallback: treat entire component as single result
    return [cmpt]
```

### Fix 6: Duplicate URLs in AI overview

**Root cause:** `knowledge.py` did `cmpt.find_all('a')` capturing all 24 `<a>` tags including duplicates from repeated UI sections (inline citations + source list + footer links).

**Change in `WebSearcher/component_parsers/knowledge.py:32-38`:**
Added `seen_urls` set deduplication, keeping first occurrence:
```python
alinks = cmpt.find_all('a')
if alinks:
    urls = DetailsList()
    seen_urls = set()
    for a in alinks:
        if 'href' in a.attrs and a['href'] != '#':
            if a['href'] not in seen_urls:
                seen_urls.add(a['href'])
                urls.append(parse_alink(a))
    details['urls'] = urls.to_dicts()
```

## Files Modified

| File | Changes |
|------|---------|
| `WebSearcher/classifiers/header_text.py` | Tag-agnostic heading search; moved "What people are saying" to perspectives |
| `WebSearcher/classifiers/main.py` | Tightened discussions_and_forums to check heading text |
| `WebSearcher/component_parsers/general.py` | Extracted `find_subcomponents()` with `PmEWq` video format |
| `WebSearcher/component_parsers/knowledge.py` | URL deduplication for AI overview |
| `WebSearcher/component_parsers/top_stories.py` | Added `get_title()` helper for multi-selector title extraction |
| `tests/test_parse_serp.py` | Full rewrite with snapshot + 8 structural tests |
| `scripts/demo_screenshot.py` | New visual inspection tool (BeautifulSoup-injected highlights) |
| `.claude/commands/parser-update.md` | New 7-phase Claude command for future parser updates |

## Tests

All tests consolidated in `tests/test_parse_serp.py` (9 tests, all passing):

1. **`test_parse_serp`** — Syrupy snapshot test, parametrized by `serp_id` from demo data
2. **`test_results_have_expected_keys`** — All results have exactly 12 expected keys
3. **`test_no_unclassified_results`** — No `type="unclassified"` (BaseResult default)
4. **`test_no_unknown_types`** — No `type="unknown"` after classifier fixes
5. **`test_no_parse_errors`** — No `error` field set in any result
6. **`test_general_results_have_title_or_url`** — General results have at least title or url
7. **`test_perspectives_have_url`** — Perspectives results have a url
8. **`test_serp_rank_is_sequential`** — `serp_rank` values are sequential from 0
9. **`test_field_types`** — Type validation for all result fields

## Verification

```bash
# Visual inspection
poetry run python scripts/demo_screenshot.py --data-dir data/demo-ws-v0.6.7a2

# Run tests
poetry run pytest tests/test_parse_serp.py -v

# Update snapshots after confirming changes are correct
poetry run pytest tests/test_parse_serp.py --snapshot-update
```

## Design Decisions

- **Tag-agnostic over tag-specific:** Used `find_all(attrs={...})` instead of adding `span` as another specific tag. Handles any future tag changes.
- **Extracted `find_subcomponents()`** over inline additions: Separates subcomponent discovery from parsing logic, making it easy to add new formats.
- **`get_title()` helper** over inline `or` chaining: Follows the existing multi-selector pattern used by `get_cite()` in the same file. Easy to extend with new selectors.
- **Single test file** over separate files: All tests share the same data loading and fixtures. Structural tests use a module-scoped `all_results` fixture for efficiency.
