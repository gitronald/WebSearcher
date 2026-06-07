---
status: active
branch: feature/v0.10.0-visible-flag
created: 2026-05-10T11:06:05-07:00
completed:
pr: https://github.com/gitronald/WebSearcher/pull/160
---

# Add a `visible` flag to parsed results

## Plan

### Motivation

Several Google components carry latent content that lives in the static HTML but is not rendered by default. Today the parser indiscriminately captures all items, mixing what was actually shown with what was lazy-loaded. This distorts any analysis that asks "what did this user see?" — visibility-aware audits, presentation-rank rankings, click-likelihood weighting, etc.

### Confirmed examples (from local stored data)

**1. perspectives — `tests/fixtures/serps-v0.6.8.json.bz2`, `qry='northern lights'`**

The "What people are saying" section has 42 items in HTML, but the last 14 sit inside a `<div style="display:none">` wrapper revealed by a "Show 2 more" button. Repro:

```bash
uv run python -c "
import bz2, json, bs4
import WebSearcher as ws

with bz2.open('tests/fixtures/serps-v0.6.8.json.bz2', 'rt') as f:
    rec = next(json.loads(line) for line in f if json.loads(line).get('qry') == 'northern lights')
parsed = ws.parse_serp(rec['html'])
pers = [r for r in parsed['results'] if r.get('type') == 'perspectives']
soup = bs4.BeautifulSoup(rec['html'], 'lxml')

hidden = 0
for p in pers:
    a = soup.find('a', href=p.get('url'))
    n = a
    while n is not None:
        if 'display:none' in (n.get('style') or '').lower().replace(' ', ''):
            hidden += 1
            break
        n = n.parent
print(f'perspectives: {len(pers)} total, {hidden} hidden')
# Expected: perspectives: 42 total, 14 hidden
"
```

The hidden items begin at the first item of the AI-themed "Aurora transforms the landscape colors" sub-section (`reddit.com/r/spaceporn/.../1o9iy76/...`). The `<div style="display:none">` wrapper has `jsname="haAclf"` and sits inside `<div jsname="olu26b">` — that's Google's "Show 2 more" container.

**1b. perspectives — preserve AI-themed sub-section context**

Beyond visibility, the same "What people are saying" carousel is *internally structured* into AI-themed sub-sections (e.g., "Historic solar storm hits Earth", "Witnessing the Aurora during darkness", "Chasing the Northern Lights", "Aurora transforms the landscape colors", "Solar flares cause stronger auroras?"). Each sub-section has both a heading and a short AI-generated summary. Items in the carousel belong to one of these sub-sections, but today's parser flattens them all into a single list, losing that grouping.

Source markup for one sub-section header:

```html
<div class="JlqpRe" jsname="lN6iy">
  <span class="JCzEY tNxQIb" jsname="r4nke">Historic solar storm hits Earth</span>
  <span class="iwY1Mb">. </span>
  <span class="WltAjf ApHyTb" jsname="VdSJob"><span class="wOJCge">
    <span class="nmhWwf OSrXXb">A historic solar storm caused rare red auroras and breathtaking displays, visible even in typically unseen locations, globally.</span>
  </span></span>
</div>
```

Selectors:
- Heading text: `span[jsname="r4nke"]` (or `span.JCzEY.tNxQIb`)
- AI summary text: `span.nmhWwf` (innermost) or `span[jsname="VdSJob"]` (outer wrapper)

Each themed sub-section's items live in their own `<div class="m5t0v XNfAUb">` carousel underneath the heading. The first carousel on the section (no theme heading above it) is the "main feed" — its items have no theme.

Proposed schema additions for items inside such grouped carousels (additive, defaults preserve existing behavior):

```json
{
  "type": "perspectives",
  "sub_rank": 13,
  "title": "...",
  "url": "...",
  "visible": false,
  "section_heading": "Historic solar storm hits Earth",
  "section_summary": "A historic solar storm caused rare red auroras..."
}
```

Items in the main feed would have `section_heading: null, section_summary: null` (or omit the keys). This is structurally distinct from the existing top-level `sub_type` (e.g., `what_people_are_saying`) which describes the *whole* component — `section_heading` describes which sub-bucket *within* the component the item belongs to.

This is a separate concern from `visible`, but tightly related: the themed sub-sections are the same DOM regions where `display:none` lazy-loading lives. Implementing both flags in the same pass through `parse_top_stories` is natural and amortizes the DOM walk.

**2. videos / top_stories — same fixture**

Carousels like `videos` typically render only the first 3 tiles by default; the rest are in HTML but hidden until the user scrolls/clicks. `top_stories` typically caps at ~7 visible stories; trailing items (sometimes 10–20 more) are present in HTML but behind expansion. Both share the same `display:none` lazy-render mechanic.

**3. Likely also affected**

`local_news`, `recent_posts`, `latest_from`, image carousels (`images`, `top_image_carousel`, `img_cards`), shopping carousels (`shopping_ads`), and the streaming-providers carousel in `available_on`.

### Goal

Add a `visible: bool` field to every parsed component (top-level rows) and to each sub-item inside `details.items` lists. Default `True`; flip to `False` when the item lives under an ancestor that hides it from initial render.

### Scope (specific parsers to update)

| Parser file | Affected `type`s | Notes |
|---|---|---|
| `WebSearcher/component_parsers/top_stories.py` | `top_stories`, `perspectives`, `local_news`, `recent_posts`, `latest_from` | One change cascades to all five — `parse_top_stories` is shared |
| `WebSearcher/component_parsers/perspectives.py` | `perspectives` | Wraps `parse_top_stories`; no extra work |
| `WebSearcher/component_parsers/local_news.py` | `local_news` | Same |
| `WebSearcher/component_parsers/recent_posts.py` | `recent_posts` | Same |
| `WebSearcher/component_parsers/latest_from.py` | `latest_from` | Same |
| `WebSearcher/component_parsers/videos.py` | `videos`, `short_videos` | Carousel tails |
| `WebSearcher/component_parsers/top_image_carousel.py` | `top_image_carousel` | Carousel tails |
| `WebSearcher/component_parsers/footer.py` (`Footer.parse_image_cards`) | `img_cards` | Carousel tails |
| `WebSearcher/component_parsers/shopping_ads.py` | `shopping_ads` | Hotel/product carousels |
| `WebSearcher/component_parsers/available_on.py` | `available_on` | Streaming-providers carousel |
| `WebSearcher/component_parsers/people_also_ask.py` | `people_also_ask` | Questions list — verify whether trailing questions are hidden |
| `WebSearcher/component_parsers/searches_related.py` | `searches_related` | Suggestion list — typically all visible, but verify |
| `WebSearcher/component_parsers/knowledge.py`, `knowledge_rhs.py` | `knowledge` | Panel content can have collapsible sub-sections |

Top-level component visibility (whether the *whole* component is rendered) is also worth tracking, but most components either render fully or not at all — so the per-item flag is the higher-value signal. Top-level can default to `True` for now and only set `False` if the component element itself is in a hidden container.

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

Add a small unit test in `tests/test_utils.py` exercising:
- Element with no style → visible
- Element with `style="display: none"` (with space) → hidden
- Element whose grandparent has `display:none` → hidden
- Element with `style="display: block; visibility: hidden"` (visibility, not display) → still considered visible (out of scope)

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

1. **Add `is_hidden` utility** in `WebSearcher/utils.py` + unit test in `tests/test_utils.py`.
2. **Update `parse_top_stories`** in `WebSearcher/component_parsers/top_stories.py` to set `visible` on each parsed sub-item. Cascades to `top_stories`, `perspectives`, `local_news`, `recent_posts`, `latest_from`. Verify against "northern lights" fixture: expect 28 visible / 14 hidden in perspectives (matches the repro above). In the same pass, add `section_heading` and `section_summary` extraction for items that live inside an AI-themed sub-section (selectors above) — emit `null` for items in the main feed.
3. **Update remaining carousel parsers** (`videos`, `top_image_carousel`, `footer.parse_image_cards`, `shopping_ads`, `available_on`) similarly.
4. **Audit remaining parsers** that emit `details.items`: `people_also_ask`, `searches_related`, `knowledge`, `knowledge_rhs`. Add `visible` only where latent content actually shows up.
5. **Add top-level `visible`** to every component dict (default `True`); only set `False` if the component element itself is inside a hidden container.
6. **Update snapshots** in `tests/__snapshots__/test_parse_serp/` — every fixture will gain `visible: true` on every row. Use `pytest --snapshot-update` to refresh.
7. **Document** the flag's semantics in the parser module docstrings and in `WebSearcher/__init__.py` if there's a top-level schema doc.

### Validation

Re-parse the demo dataset and the bz2 fixtures to verify:

```bash
# 1. Demo dataset (parsed.json is JSONL of one parsed dict per SERP)
uv run python -c "
import json, WebSearcher as ws
with open('data/demo-ws-v0.6.10a0/serps.json') as f:
    serps = [json.loads(line) for line in f if line.strip()]
n_visible = n_hidden = 0
for rec in serps:
    for r in (ws.parse_serp(rec['html']).get('results') or []):
        if r.get('visible', True): n_visible += 1
        else: n_hidden += 1
        for it in ((r.get('details') or {}).get('items') or []):
            if isinstance(it, dict):
                if it.get('visible', True): n_visible += 1
                else: n_hidden += 1
print(f'visible: {n_visible}, hidden: {n_hidden}')
"

# 2. Spot-checks on specific queries
# - 'northern lights' (v0.6.8 fixture): perspectives 28 visible / 14 hidden
# - 'albert einstein' (demo): perspectives gained 11 items via the role=listitem fix; check how many are hidden
# - 'taylor swift' (demo): perspectives gained 14; same check
# - 'houston news today' (demo): local_news gained 8; same check
```

Total component count should be unchanged from the current parser; the `visible: false` rows are new metadata, not new rows.

### Out of scope

- CSS-rule-based or JS-driven hiding detection
- Distinguishing "fully hidden" vs "partially clipped" (e.g., overflow:hidden carousel tails) — both treated as hidden if `display:none` is present, otherwise visible
- Tracking visibility *changes* across SERP variants (this captures static HTML at the time of crawl)
- Ranking adjustments based on visibility — a separate downstream concern
- Filtering / removing hidden items entirely — the flag preserves them with metadata; consumers decide

## Log

### 2026-06-06 — Activation & adaptation (plan was outdated)

Activated on `feature/v0.10.0-visible-flag` (off the `feature/v0.10.0` integration branch). The plan was drafted 2026-05-10 at ~v0.6.8; the codebase has since moved to v0.10.0a0. Re-grounded the spec against current reality before implementing:

- **Backend migration (plan 026): bs4 → selectolax.** The `is_hidden(elem: bs4.element.Tag)` utility in the spec uses the wrong API. Ported to `selectolax.lexbor.LexborNode`: walk `node.parent` and read `(node.attributes.get("style") or "")`. Verified the port reproduces the headline evidence exactly.
- **Fixture renamed/consolidated (plan 032):** `tests/fixtures/serps-v0.6.8.json.bz2` no longer exists; the corpus is now `tests/fixtures/serps.json.bz2`. `'northern lights'` is still present. All repros/validation in this plan should use the new path.
- **Headline evidence re-confirmed against current parser:** perspectives on `'northern lights'` = 42 total, 14 hidden via the `display:none` ancestor walk (28 visible / 14 hidden), matching the original spec.
- **`section`/`sub_type` already shipped** on perspectives rows (`section='main'`, `sub_type='what_people_are_saying'`) — independent of this work.
- **Precedent: `ads.py` already does hidden-detection but with the opposite philosophy** — it *filters and drops* hidden carousel cards via Google attrs (`data-has-shown="false"`, `data-viewurl`), whereas this plan *keeps and flags* (`visible: false`). Ads is outside this plan's scope table, so they coexist.

### 2026-06-06 — Evidence reconciliation: perspectives is 30 visible / 12 hidden (not 28/14)

The schema mechanism is `BaseResult` (`WebSearcher/models/data.py`): every parsed row is round-tripped through `BaseResult(**row).model_dump()` in `components.py`, which drops unknown keys — so `visible` had to be added as a real model field (`visible: bool = Field(True, ...)`). Nested `details.items` survive untouched (free-form `details` dict). The detection of *whole-component* hiding remains deferred (everything defaults `visible=True`; only per-item parsers flip to `False`).

The corrected count for `'northern lights'` perspectives is **30 visible / 12 hidden**, not the plan's 28/14. The DOM has exactly **one** `<div style="display:none" jsname="haAclf">` wrapper containing **12** `role="listitem"` cards. The parser flags exactly those 12 (a contiguous tail, sub_rank 30–41). The first hidden card is `reddit.com/r/spaceporn/comments/1o9iy76/...` — exactly the "Aurora transforms the landscape colors" sub-section boundary the plan named, so the boundary is correct. The plan's original "14" was an artifact of its bs4 anchor-href walk (`css_first('a[href=...]')` matched 2 extra hidden duplicate anchors); the structurally-correct count walking from the emitted card nodes is 12.

**Scope decisions for this implementation (user-confirmed):**

- **Defer section 1b** (`section_heading`/`section_summary` AI-themed sub-section split) to its own plan. The perspectives landscape shifted (now carries `section`/`sub_type`) and the sub-section selectors need fresh verification. This PR ships only the `visible` flag.
- **Verified core first:** `is_hidden` util + the `parse_top_stories` family (`top_stories`, `perspectives`, `local_news`, `recent_posts`, `latest_from`) + the obvious carousels (`videos`, `short_videos`, `top_image_carousel`, `footer.parse_image_cards`, `shopping_ads`, `available_on`). Audit `people_also_ask`, `searches_related`, `knowledge`, `knowledge_rhs` and add `visible` only where latent content actually exists.

### 2026-06-06 — Audit-group result: no changes needed

Audited the four "verify" parsers against the full fixture corpus (`tests/fixtures/serps.json.bz2`):

- **`people_also_ask`** — 264 questions across the corpus, **0** under `display:none`. `details.items` are plain strings (no dict to carry a `visible` key). No action.
- **`searches_related`** — 640 suggestion items (`a.k8XOCe` / `div.EASEnb` / `a.ngTNl`), **0** hidden. Items are plain strings. No action.
- **`knowledge` / `knowledge_rhs`** — knowledge panels do contain `display:none` links (56 across 22 panels), but those are UI chrome / tab content the parser does not emit. Of the **18** emitted dict-items, 0 carry a URL and 0 map to a hidden anchor (the other 24 items are strings). No emitted item is ever latent. No action.

All four still receive `visible: true` on their top-level rows via the `BaseResult` default. Per-item flagging adds no signal here, so the audit group is left unchanged. Carousels gained one parser beyond the plan's table: `short_videos` (same lazy-load mechanic).

### 2026-06-06 — Implementation summary

Shipped on `feature/v0.10.0-visible-flag` (PR #160), commits:

- `is_hidden` helper in `WebSearcher/_slx.py` (selectolax ancestor walk for inline `display:none`) + `tests/test_slx.py` (5 cases).
- `visible` field added to `BaseResult` (`WebSearcher/models/data.py`, default `True`) — the schema mechanism: `components.py` round-trips every row through `BaseResult(**row).model_dump()`, which had been dropping the key.
- Per-item flag set in: `top_stories.py` (`parse_top_story`, cascades to `perspectives`/`local_news`/`recent_posts`/`latest_from`), `videos.py`, `short_videos.py`, `shopping_ads.py` (all three card parsers), and the nested-`details.items` carousels `top_image_carousel.py`, `available_on.py`, `footer.py` (`parse_img_card` — both the card row and each image item).
- Audit group (`people_also_ask`, `searches_related`, `knowledge`, `knowledge_rhs`): no changes — no emitted item is ever latent (see audit entry above).
- `EXPECTED_KEYS` in `tests/test_parse_serp.py` updated to include `visible`; all 87 parse-serp snapshots refreshed (provably additive: 0 net removed lines, only `visible` keys added).

Validation: full suite **462 passed**. Fixture corpus: 2268 visible / 42 hidden (all `perspectives`). Demo dataset (`data/demo-ws-v0.6.10a0`): 1309 visible / 72 hidden (all `perspectives`); `'northern lights'` 30/18, `'taylor swift'` 30/12, `'albert einstein'` 30/18, `'houston news today'` perspectives 19/0 + local_news 15/0.

Deferred (own plans): section 1b (`section_heading`/`section_summary` AI-themed sub-section split) and active whole-component top-level visibility detection.

## Retrospective
