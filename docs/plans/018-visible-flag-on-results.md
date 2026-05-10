---
status: draft
branch: feature/visible-flag
created: 2026-05-10T11:04:25-07:00
completed:
pr:
---

# Add a `visible` flag to parsed results

## Plan

### Motivation

Several Google components carry latent content that lives in the static HTML but is not rendered by default. Examples seen on the demo dataset:

- **perspectives** ("northern lights" SERP): the "What people are saying" section has 42 items in HTML; only ~30 are visible. The remaining ~12 sit inside a `<div style="display:none">` wrapper revealed by a "Show 2 more" button.
- **videos**: typical layout shows 3 thumbnails by default; the rest of the carousel is in HTML but hidden until the user scrolls.
- **top_stories**: typical layout caps at ~7 visible stories; trailing items (sometimes 10–20 more) are present in HTML but require expansion.
- Likely also: **local_news**, **recent_posts**, **latest_from**, image and shopping carousels.

Today the parser indiscriminately captures all items, mixing what was actually shown with what was lazy-loaded. This distorts any analysis that asks "what did this user see?" — visibility-aware audits, presentation-rank rankings, click-likelihood weighting, etc.

### Goal

Add a `visible: bool` field to every parsed component (top-level rows) and to each sub-item inside `details.items` lists. Default `True`; flip to `False` when the item lives under an ancestor that hides it from initial render.

### Scope (parsers to update)

- `top_stories.parse_top_stories` — feeds `top_stories`, `perspectives`, `local_news`, `recent_posts`, `latest_from`. One change unlocks five component types.
- `videos.parse_videos` — carousel items
- `images` carousel — likely also hidden trailing items
- `shopping_ads` — hotel/product carousels
- `available_on` — providers carousel (~7 items, may scroll)
- Re-evaluate every parser that emits a `details.items` list

Top-level component visibility (whether the *whole* component is rendered) is also worth tracking, but most components either render fully or not at all — so the per-item flag is the higher-value signal. Top-level can default to `True` for now.

### Visibility detection

Heuristic: an element is hidden if any ancestor has inline `style` containing `display:none` (whitespace-tolerant). This catches:

- Lazy-loaded carousel tails (Google's standard pattern)
- "Show more" expansion containers (the perspectives case)
- Off-screen UI elements that render only on interaction

Not caught (acceptable false negatives):
- CSS-rule-based hiding (e.g., `.collapsed { display: none }` in a stylesheet) — would require running CSS, out of scope
- Visibility controlled by JS at runtime — same

Implementation as a small utility in `WebSearcher/utils.py`:

```python
def is_hidden(elem: bs4.element.Tag | None) -> bool:
    """True if elem or any ancestor has inline style display:none."""
    while elem is not None:
        style = (elem.get("style") or "").lower().replace(" ", "")
        if "display:none" in style:
            return True
        elem = elem.parent
    return False
```

### Schema additions

Top-level row (every component type):
```json
{
  "type": "...",
  "visible": true,
  ...
}
```

Sub-items inside `details.items` (when present):
```json
{
  "details": {
    "type": "hyperlinks",
    "items": [
      {"url": "...", "text": "...", "visible": true},
      {"url": "...", "text": "...", "visible": false}
    ]
  }
}
```

Default `visible: True` everywhere it isn't explicitly determined — preserves backwards compatibility for downstream consumers that don't look at the flag.

### Implementation order

1. Add `is_hidden` utility + unit test against a small fixture.
2. Update `parse_top_stories` to set `visible` per sub-item. Cascades to `top_stories`, `perspectives`, `local_news`, `recent_posts`, `latest_from`. Verify against "northern lights" demo: expect ~30 visible / ~12 hidden in perspectives.
3. Update `videos`, `images`, `shopping_ads`, `available_on` parsers similarly.
4. Add top-level `visible` to every component dict (default `True`); only set `False` if the component itself is in a hidden container.
5. Update `tests/__snapshots__` — many fixtures will gain `visible` keys.
6. Document the flag's semantics in the parser docstrings.

### Validation

- Re-parse the v0.6.10a0 demo dataset; expect total component count unchanged but `visible: false` rows appear.
- Spot-check on `northern lights` (perspectives), `albert einstein` (perspectives — also gained items behind hidden), `houston news today` (local_news — gained 8 items behind hidden), and `taylor swift` (perspectives gained 14).
- Compare visible-only vs visible+hidden counts to estimate how widespread latent content is across the dataset.

### Out of scope

- CSS-rule-based or JS-driven hiding detection
- Distinguishing "fully hidden" vs "partially clipped" (e.g., overflow:hidden carousel tails) — both treated as hidden if `display:none` is present, otherwise visible
- Tracking visibility *changes* across SERP variants (this captures static HTML at the time of crawl)
- Ranking adjustments based on visibility — a separate downstream concern

## Log

## Retrospective
