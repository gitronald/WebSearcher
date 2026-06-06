---
status: done
branch: dev
created: 2026-05-10T17:18:39-07:00
completed: 2026-05-10T17:34:49-07:00
pr: https://github.com/gitronald/WebSearcher/pull/113
---

# Directives reparse audit fixes

Investigate local parse-diff items and fix the regressions and gaps it surfaced.

## Plan

The report flagged five items for investigation:

1. `general -> unknown` regression on media/TV/anime queries (~11k rows)
2. `knowledge` row loss on entity queries (~13.7k rows)
3. `searches_related -> knowledge` reclassification (11.4k rows; "largest single transition")
4. `ad +4` per-SERP pattern on travel queries (+1,257 rows)
5. Empty `jobs` and `flights` extraction (480 rows with null title/url)

Work through each item against the live crawl HTML and resolve.

### Items 1, 2, 3 — same root cause

A single bug in `ExtractorMain.is_dictionary_header` was responsible for all
three. The predicate matched ANY `kp-wholepage-osrp` wrapper containing a
`[data-attrid="title"]` element, intending to skip duplicate dictionary
headers. In practice it dropped the top-of-page knowledge panel for movie,
person, athlete, finance, streaming, and news-event SERPs as well.

The dropped row shifted every subsequent row's `serp_rank` by -1. Joining v1
and v2 on `(serp_id, serp_rank)` then produced phantom transitions:
v1 general at rank N collided with v2 unknown at rank N (because v2's rank N
was v1's rank N+1, which was already unknown); v1 `searches_related` at the
bottom collided with v2 `knowledge / panel_rhs` — etc.

**Fix:** Tighten `is_dictionary_header` to require that the rso column also
contain a dictionary-specific marker (`data-attrid="DictionaryHeader"` or
`role=button` text `"Dictionary"`). Verified on fixtures and the directives
crawl that this preserves dedup for real dictionaries (e.g.
`define serendipity`) and recovers the entity panel for everything else.

Bundled with the same commit: normalize whitespace in knowledge-panel text
fields. `utils.get_text(..., strip=True)` was calling `.strip()` on the joined
result, which trimmed edges but left internal whitespace runs. Pass `strip`
through to bs4's native per-node strip so titles like the zhivago entity
header collapse from 165 chars of jumbled spacing to 123 chars of clean prose.

Affects: `WebSearcher/extractors/extractor_main.py`,
`WebSearcher/utils.py`, `WebSearcher/component_parsers/knowledge.py`.

### Item 4 — ad +4 pattern

The +1,257 row gain on travel queries was a legitimate improvement: v1
emitted one row per ad-block, v2 correctly emits each individual ad as its
own sub-row with distinct titles.

The reverse case (`gu gels`: v1 1 ad row, v2 0 ad rows) surfaced a separate
bug. `parse_ads` dispatched on the FIRST matching ad sub-type and ignored
the rest. A `#tads` block containing both a shopping carousel
(`commercial-unit-desktop-top`) AND a standard text ad (`uEierd`) only got
the shopping carousel parsed.

**Fix:** `parse_ads` now iterates every selector in `AD_SUBTYPE_SELECTORS` and
aggregates results, so both layouts emit. Verified on `gu gels` (recovers
the dropped "Shop GU Energy Gels" text ad) and on the +4 travel queries
(still emits 5 distinct ads).

Affects: `WebSearcher/component_parsers/ads.py`.

### Item 5 — jobs and flights extraction

Both component types were classified correctly but had no registered parser,
so they fell through to `parse_not_implemented` which emits a single row
with `title=null, url=null` and a raw `<|>`-joined text dump.

**Fix:** Add thin `parse_jobs` and `parse_flights` parsers that extract the
section heading as `title` and structured items into `details`:

- `parse_jobs`: items = list of aria-level=3 headings (job titles)
- `parse_flights`: items = list of `{url, text}` for the route links

Also added a `flights` `ComponentType` to the registry (it was previously
missing, so `flights` type wasn't even reaching the parser dispatch table).

Affects: `WebSearcher/component_parsers/jobs.py` (new),
`WebSearcher/component_parsers/flights.py` (new),
`WebSearcher/component_parsers/__init__.py`,
`WebSearcher/component_types.py`.

### Bonus — knowledge_subcard classifier

While investigating item 2 on the `doctor zhivago` SERP, identified four
additional `unknown` rows that were entity-panel extension subcards (Cast,
Trailers & clips, Based on the book, Reviews). Trailers & clips fit the
videos pathway cleanly (new `ClassifyMain.videos` classifier emitting
`sub_type="trailers-and-clips"`); the others share a structural pattern
(`JNkvid` wrapper + `aria-level=2` heading) that catches all current AND
future entity-panel sections generically.

`ClassifyMain.knowledge_subcard` emits `type="knowledge"` with `sub_type`
derived from the slugified heading text. `parse_knowledge_panel` gets a new
elif branch that fills `title` from the heading, captures aria-level=3
headings as `details.items` (clean per-actor / per-section text), and drops
the noisy `/search?stick=...` Google KG navigation URLs from `details.urls`.

Affects: `WebSearcher/classifiers/main.py`,
`WebSearcher/component_parsers/videos.py`,
`WebSearcher/component_parsers/knowledge.py`.

### Regression fixtures

Captured three new SERPs as bz2-compressed JSONL fixtures with an inline
`note` field documenting provenance:

- `serps-v0.7.2-knowledge-subcards.json.bz2` -- doctor zhivago (KP recovery + subcard classifier + videos)
- `serps-v0.7.2-ads.json.bz2` -- gu gels (mixed ad layouts) + central park new york (5-ads carousel)
- `serps-v0.7.2-jobs.json.bz2` -- koch hiring mississippi (jobs widget)

All test_parse_serp snapshots regenerated. 233 tests passing.

## Log

Commits on `dev` in chronological order:

- `7a2c4b0` -- update knowledge panel extraction and text whitespace normalization
- `013404a` -- add videos classifier and trailers-and-clips sub_type
- `5a480d4` -- add knowledge_subcard classifier for entity-panel sections
- `4303676` -- update parse_ads to capture mixed ad layouts and add regression fixtures
- `cb80f1e` -- add jobs and flights parsers

## Retrospective

### Before/after results

| fix | commit | sample | field | before | after |
|---|---|---|---|---|---|
| 1. KP recovery | `7a2c4b0` | doctor zhivago rank 0 | type / title | `general / 'Doctor Zhivago (film)'` | `knowledge / 'Doctor Zhivago 1965 ‧ Romance/War ‧ 3h 17m Overview Cast …'` |
| 2. Whitespace normalize | `7a2c4b0` | zhivago KP title len | title len | 165 chars; `'       Doctor Zhivago    1965 ‧ Romance/War …    Overview Cast …'` | 123 chars; `'Doctor Zhivago 1965 ‧ Romance/War ‧ 3h 17m Overview Cast …'` |
| 3. Videos classifier | `013404a` | zhivago rank 5 | type / sub_type | `general / None` (shifted general result) | `videos / 'trailers-and-clips'` (4 YouTube subrows) |
| 4. knowledge_subcard | `5a480d4` | zhivago Cast subcard | type / sub_type / details.items | `people_also_ask / None / —` (was unknown then shifted) | `knowledge / 'cast' / [Julie Christie, Omar Sharif, Geraldine Chaplin, … 7 actors]` |
| 5. parse_ads multi-type | `4303676` | gu gels #tads block | ad rows emitted | 0 ad rows (shopping carousel parsed; text ad dropped) | 1 ad row: `sub_type='submenu' title='Shop GU Energy Gels'` + 3 shopping_ads |
| 6. parse_jobs/flights | `cb80f1e` | koch hiring mississippi | title / details | `title=None / url=None / text='Jobs<|>Filters List<|>Find in-demand jobs<|>…'` | `title='Jobs' / details.items=['Electrical and instrumentation', 'Woodyard Day Technician', 'Pullet Crew Member']` |

### Notes

- Items 1, 2, and 3 from the report turned out to be a single root-cause bug.
  The (serp_id, serp_rank) join in the report inflated one missing-row event
  into thousands of phantom type transitions. Worth flagging in any future
  comparison: missing/extra rows between versions cascade into spurious
  type-change counts via positional joins. Compare on stable keys (component
  signature or content hash) rather than rank when row counts differ.

- The `is_dictionary_header` predicate had an overly broad first condition
  (`kp-wholepage-osrp` wrapper class) used to gate a second over-broad
  condition (`[data-attrid="title"]`). The "structural" fix (the inline
  DictionaryHeader marker in rso) is also the semantic fix -- skip the
  wrapper ONLY when the duplicate would actually arise.

- The `general` classifier's `format-04` (`cmpt.find("div", {"class": ["g",
  "Ww4FFb"]})`) over-matches on `Ww4FFb` anywhere inside a component,
  pulling brand-explore and similar widgets into `general` with null
  title/url. Mitigated by setting `error="no title or url"` in
  `parse_general_result` when neither field can be extracted (so the
  structural test skips these rows). The classifier itself could be
  tightened in a future change.
