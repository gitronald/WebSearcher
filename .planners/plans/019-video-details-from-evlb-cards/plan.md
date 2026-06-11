---
id: 19
slug: video-details-from-evlb-cards
status: active
branch: feature/v0.10.0-evlb-video-details
created: 2026-05-10T12:31:46-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/167
---

# Enrich video details from hidden `evlb_*` "About this result" cards

## Plan

### Motivation

The `general[sub_type=video]` parser currently relies on stale selectors (`.gqF9jc` for source, `.JIv15d` for duration) that match nothing in modern Google SERPs — `details.source` and `details.duration` always come out `None`, which is why we dropped the empty payload entirely. (See the existing TODO: "`general[sub_type=video]` source/duration selectors are stale".)

Google's modern SERPs still embed the richer video metadata into the static HTML, just not on the visible tile. It lives in a hidden `<div id="evlb_..." style="display:none">` card per video — the "About this result" panel that fires open when the user clicks the ⋮ icon next to the tile. These cards contain a clean title, channel/uploader name, source ("YouTube"), publish date, and thumbnail URL.

Survey across the "northern lights" SERP (`tests/fixtures/serps-v0.6.8.json.bz2`):

- 6 `evlb_*` elements total, 5 populated, 1 empty template stub
- 3 cards attached to the 3 visible videos in the `videos` component
- 2 cards attached to YouTube videos that landed inside the `perspectives` carousel
- **All evlb_* cards are video-specific** — no other result type pre-renders its info card into the static HTML

Selectors confirmed present in the modern markup (inside each `evlb_*`):

| Field | Selector |
|---|---|
| Clean title | `h1.WQWxe` |
| Source ("YouTube") | `span.KrMNbf` |
| Channel / uploader | `span.PNsAZd` |
| Publish date | `span.DKsccc` |
| Thumbnail URL | `img.aLL3sb[src]` |
| Card root | `div.F9x6yb` |

Today's `parse_general_video` in `WebSearcher/component_parsers/general.py` uses `.gqF9jc` (source) and `.JIv15d` (duration) — both 0 hits on current SERPs.

### Goal

Extract `source`, `channel`, `publish_date`, `thumbnail_url`, and re-establish a non-null `details.type="video"` payload by reading from the hidden `evlb_*` card associated with each video result.

### Scope

1. **`general[sub_type=video]`** — `WebSearcher/component_parsers/general.py`'s `parse_general_video`. Find the associated `evlb_*` card for each tile and merge fields.
2. **`videos` component** — `WebSearcher/component_parsers/videos.py`. Each tile in the carousel has its own `evlb_*` card sibling/descendant. Same approach.
3. **`perspectives` and similar carousels** (`top_stories.parse_top_stories`) — YouTube items here can also have `evlb_*` cards. Lower priority; measure coverage gain on the demo set before wiring up.

### Approach

Add a small utility (likely in `WebSearcher/utils.py` or a new `WebSearcher/component_parsers/_video_card.py`):

```python
import re
import bs4
from ..utils import get_text

def parse_evlb_card(scope: bs4.element.Tag) -> dict | None:
    """Extract video metadata from a hidden 'About this result' card inside `scope`."""
    card = scope.find(id=re.compile(r"^evlb_"))
    if not card:
        return None
    img = card.find("img", class_="aLL3sb")
    fields = {
        "title": get_text(card, "h1", {"class": "WQWxe"}),
        "source": get_text(card, "span", {"class": "KrMNbf"}),
        "channel": get_text(card, "span", {"class": "PNsAZd"}),
        "publish_date": get_text(card, "span", {"class": "DKsccc"}),
        "thumbnail_url": img.get("src") if img else None,
    }
    fields = {k: v for k, v in fields.items() if v}
    return fields or None
```

In each video parser, after the existing extraction:

1. Call `parse_evlb_card(tile)` scoped to the tile's container.
2. If it returns a dict, set `details = {"type": "video", **fields}`.
3. Otherwise leave `details = None` (matching today's post-cleanup behavior).

Caveats:

- The cards live inside `display:none` ancestors. They are intentionally not visible — this is a *data*-side enrichment, not a visibility flip. Don't tag `visible=true` based on this; plan 018 handles visibility orthogonally.
- Some thumbnail URLs are `data:image/...` base64 placeholders for lazy loading. Capture them as-is; downstream consumers can filter `data:` URLs if they want real thumbnails.

### Implementation order

1. Add `parse_evlb_card` helper + a small unit test against the `northern lights` fixture (assert expected channel/date/source for the 3 visible videos).
2. Wire into `parse_general_video` in `WebSearcher/component_parsers/general.py`.
3. Wire into the `videos` component parser (`WebSearcher/component_parsers/videos.py`).
4. Drop the stale `.gqF9jc` / `.JIv15d` selectors and the helper that no longer fires once the new path covers the same fields with non-null values across the demo set.
5. Optionally extend to perspectives YouTube items — measure incremental coverage gain on the demo dataset first.
6. Update snapshots in `tests/__snapshots__/test_parse_serp/` — `video` details will go from `null` (post-recent-cleanup) to populated.
7. Mark the existing TODO ("`general[sub_type=video]` source/duration selectors are stale") complete and link this plan from the closed entry.

### Validation

Re-parse `tests/fixtures/serps-v0.6.8.json.bz2` (northern lights query) and confirm:

```bash
uv run python -c "
import bz2, json, WebSearcher as ws
with bz2.open('tests/fixtures/serps-v0.6.8.json.bz2', 'rt') as f:
    rec = next(json.loads(line) for line in f if json.loads(line).get('qry') == 'northern lights')
for r in ws.parse_serp(rec['html'])['results']:
    if r.get('type') == 'videos':
        print(r.get('title'), '->', r.get('details'))
"
```

Expected: 3 videos with non-null `details.source='YouTube'`, `channel` populated (e.g., "GeologyHub", "Late Night Astronomy", "Robservatory"), `publish_date` populated, `thumbnail_url` populated.

Same check on `data/demo-ws-v0.6.10a0/serps.json` — any SERP with a `videos` component should now have rich `details` populated for each tile.

### Out of scope

- "Show more videos" expansion (JS-driven on click; not in static HTML)
- Non-video result types — the `evlb_*` mechanism is video-specific (verified: 108 "About this result" trigger buttons across a SERP, but only ~5 rich cards pre-rendered, all videos)
- `duration` — the field doesn't appear in `evlb_*` cards; keep it dropped, or revisit later by scraping the visible tile's duration overlay (a separate selector hunt)

## Log

### 2026-06-10 — activation: evidence re-grounded on current fixture corpus

Re-verified the plan's evidence at component level through the real pipeline
(`Extractor` + `classify_component`) before starting. The fixture has been
renamed since drafting: `tests/fixtures/serps.json.bz2` (87 SERPs), not
`serps-v0.6.8.json.bz2`. Findings:

- All six selectors confirmed on populated cards (`h1.WQWxe`, `span.KrMNbf`,
  `span.PNsAZd`, `span.DKsccc`, `img.aLL3sb[src]`, `div.F9x6yb`).
- `northern lights` matches the plan exactly: 6 cards, 5 populated — 3 in
  `videos`, 2 in `perspectives`.
- Association assumption verified corpus-wide: every populated card is a
  descendant of exactly one tile, and no tile holds more than one populated
  card (checked for `general` PmEWq tiles and `videos` carousel tiles).
- Coverage is broader than scoped: populated cards also appear inside
  `short_videos`, `people_also_ask`, and `knowledge` components (still all
  YouTube video cards). Older SERPs in the corpus carry only empty card stubs
  (0 populated), so the helper's `None`-on-empty path is exercised.
- The codebase migrated bs4 -> selectolax (plan 026) after this plan was
  drafted; the helper sketch translates to `_slx` helpers and `Node.css_first`.

Repro: parse any fixture SERP and inspect components, e.g.

```bash
uv run python -c "
import bz2, json
import WebSearcher as ws
with bz2.open('tests/fixtures/serps.json.bz2', 'rt') as f:
    rec = next(r for line in f if (r := json.loads(line))['qry'] == 'northern lights')
soup = ws.make_soup(rec['html'])
ex = ws.Extractor(soup)
ex.extract_components()
for c in ex.components:
    c.classify_component()
    n = len(c.elem.css('div[id^=evlb_] h1.WQWxe'))
    if n: print(c.type, n)
"
```

### 2026-06-10 — implementation

Branch `feature/v0.10.0-evlb-video-details` off `feature/v0.10.0`; draft PR
opened. Commits: `add video details from hidden evlb cards`, `add video card
tests and update snapshots`.

- New `WebSearcher/component_parsers/_video_card.py` with `parse_evlb_card`
  (selectolax port of the bs4 sketch; iterates cards in scope and returns the
  first that yields a field, so an empty stub before a populated card cannot
  shadow it). Returns fields only; callers write the literal
  `{"type": "video", **fields}` at the call site.
- Wired into `parse_general_video` (`general.py`) and `parse_video`
  (`videos.py`; content details set before `mark_timestamp_row` /
  `mark_hidden_row` so timestamp/visible ride as sibling keys).
- **Deviation from step 4:** the plan claimed both legacy selectors were dead,
  but snapshot diffs showed `.JIv15d` (duration) still fires on 18 rows from
  older SERPs in the fixture corpus — the plan's own removal gate ("once the
  new path covers the same fields") is unmet for `duration`, so the selector
  stays as a merged fallback in `parse_general_video`. Only `.gqF9jc` (source,
  0 hits corpus-wide) was dropped. Net effect on legacy rows: they keep
  `duration` and lose only the hollow `source: null` key.
- `demos/show.py` video summary now renders source · channel · publish_date.
- 44 video rows enriched across 28 snapshot files; full suite 482 passed,
  ruff and pyrefly clean. Demo capture (`data/demo-ws-v0.10.0a0/serps.json`):
  the only 2 video rows present are both fully enriched.
- Step 5 (perspectives/top_stories wiring) not done: populated cards also sit
  in `perspectives`, `short_videos`, `people_also_ask`, and `knowledge`
  components corpus-wide — broader than the plan scoped; left for a follow-up
  measure-first pass.
- Step 7 is moot: the legacy `TODO.md` was retired in the `.planners/`
  migration, so this plan is itself the tracking item for the stale-selector
  TODO.

## Retrospective
