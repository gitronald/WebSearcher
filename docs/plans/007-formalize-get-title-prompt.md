---
status: done
branch: dev
created: 2026-02-22T12:56:12-08:00
completed: 2026-02-06T10:18:38-08:00
pr: https://github.com/gitronald/WebSearcher/pull/94
---

# Implement `get_text_by_selectors` refactor across WebSearcher

Branch: `update/get-text-by-selectors`

You are implementing the plan at `.claude/plans/formalize-get-title.md`. The goal is to centralize the "try multiple CSS selectors, return first non-null text" pattern into a single `get_text_by_selectors()` utility function, then update 7 component parsers to use it. Read each file before editing.

## Phase 1 — Add the utility function (must complete before Phase 2)

Edit `WebSearcher/webutils.py` — add this function after `get_link_list()` (around line 162), before `find_all_divs`:

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

No new imports needed — `Tag`, `Mapping`, `Any`, `get_text` are already in scope.

## Phase 2 — Update all 7 parsers (run in parallel)

All files are in `WebSearcher/component_parsers/`. Read each file before editing. For each:
- Add module-level selector constant(s) after imports
- Replace the old pattern with a `get_text_by_selectors` call
- Delete the now-unused local function (if any)

### 2a. `top_stories.py`

Add `get_text_by_selectors` to the `from ..webutils import` line. Add `TITLE_SELECTORS = [('div', {'class': 'n0jPhd'}), ('div', {'class': 'eAaXgc'})]` after imports. Replace `get_title(sub)` call with `get_text_by_selectors(sub, TITLE_SELECTORS)`. Delete the local `get_title()` function.

### 2b. `discussions_and_forums.py`

Uses `from .. import webutils` (no import change). Add `TITLE_SELECTORS` and `CITE_SELECTORS` constants after imports. Replace `get_title(cmpt)` → `webutils.get_text_by_selectors(cmpt, TITLE_SELECTORS)`, `get_cite(cmpt)` → `webutils.get_text_by_selectors(cmpt, CITE_SELECTORS)`. Delete local `get_title()` and `get_cite()`.

### 2c. `map_results.py`

Uses `from .. import webutils` (no import change). Add `TITLE_SELECTORS = [('div', {'class': 'aiAXrc'})]` after imports. Replace `get_title(cmpt)` → `webutils.get_text_by_selectors(cmpt, TITLE_SELECTORS)`. Delete local `get_title()` including commented-out line.

### 2d. `people_also_ask.py`

Uses `from .. import webutils` (no import change). Add `QUESTION_SELECTORS` (5 entries: `rc`, `yuRUbf`, `iDjcJe`, `JlqpRe`, `cbphWd`). Replace entire `parse_question()` body with `return webutils.get_text_by_selectors(question, QUESTION_SELECTORS, strip=True)`.

### 2e. `local_results.py`

Uses `from .. import webutils` (no import change). Add `HEADER_SELECTORS = [("h2", {"role": "heading"}), ("div", {"aria-level": "2", "role": "heading"})]`. Replace the 6-line `header_list` block with: `header = webutils.get_text_by_selectors(cmpt, HEADER_SELECTORS)` then `if header: sub_type = header.lower().replace(" ", "_")`.

### 2f. `searches_related.py`

Same `HEADER_SELECTORS` constant. Replace the 5-line `header_list` block with: `header = webutils.get_text_by_selectors(cmpt, HEADER_SELECTORS)` then `parsed['sub_type'] = header.lower().replace(" ", "_") if header else None`.

### 2g. `ads.py`

Add `AD_STANDARD_TEXT_SELECTORS = [('div', {'class': 'yDYNvb'}), ('div', {'class': 'Va3FIb'})]` after existing `SUB_TYPES` constant. In `_parse_ad_standard_text()`, replace the `name_attrs` loop with `text = webutils.get_text_by_selectors(sub, AD_STANDARD_TEXT_SELECTORS)`. Keep the `label` line and return statement unchanged.

## Phase 3 — Verify (after all edits)

1. Run `poetry run pytest tests/ -q` — all tests must pass
2. Run the reparse check from the plan (parse demo SERPs, confirm no errors)
3. Run the targeted component type check from the plan (print titles for affected types)

## Phase 4 — Commit

Stage all 8 modified files and commit with message following project conventions (lowercase, short, no special characters). Do not push.