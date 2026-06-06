---
status: proposed
branch: TBD
created: 2026-06-01
---

# `_ComponentSignals` consolidation + extractor hot-path review

Follow-up to [plan 035](035-get-text-native-fastpath.md). With the `get_text`
native fast path banked (~7% off `parse_serp`), the profile's #2 *optimizable*
cost is now `classifiers/main.py:_ComponentSignals.__init__`, and the extractor
phase is the largest unprofiled-in-detail bucket worth a pass. This plan scopes
both. Same methodology as plans 023/035: per-SERP median + MAD, gate on the
run-to-run noise floor (~0.3-0.5% on the current idle box), and trust only
**back-to-back same-session A/B** numbers.

## Current baseline (Python 3.13.12, 87-SERP corpus)

From plan 035's profile (`bench_parse.py --profile`, 870 parses, post-fast-path):

| Frame | self | nature |
|---|---|---|
| `make_soup` (lexbor parse) | 10.1 s (~20%) | structural -- one parse/SERP |
| `_ComponentSignals.__init__` | 5.1 s; 6.7 s cum (**~13%**) | pure-Python, **this plan** |
| `_iter_text_fragments` (residual walker) | 2.2 s; 3.5 s cum | already optimized in 035 |
| `_get_dom_positions` | 1.5 s | full-document `css('*')` walk |
| `_ai_overview_payloads._iter_payload_blobs` | 1.6 s; 2.1 s cum | recent addition |
| `is_valid` (`extractor_main.py:568`) | 1.0 s; 1.8 s cum | extraction |
| `extract_from_standard` (`extractor_main.py:333`) | 0.8 s; 2.4 s cum | extraction |

## Lever 1: `_ComponentSignals` (primary)

`ClassifyMain.classify` builds a `_ComponentSignals` per main component -- one
`cmpt.css('*')` descendant walk that fills three sets (class tokens, ids, tag
names), feeding the necessary-signal preconditions on the classifier chain
(plan 023 item 3a). It is called ~13x/parse (11,390 over 870 parses) and is now
~13% of parse time. The cost is the per-element Python loop:
`set.update(cls.split())` (1.67M updates), `set.add(tag)` (2.47M adds),
`str.split` (1.72M), `el.attrs.get`/`el.id`/`el.tag` per element.

Candidate directions (each must stay byte-identical -- preconditions are
*necessary* conditions, so any change must not drop a real signal; pin with the
87-snapshot suite, no updates):

1. **Build only the signals the chain actually consults.** The `names` set is
   queried for ~8 custom-element tags (`g-scrolling-carousel`, `g-tray-header`,
   `block-component`, `h2`, `promo-throttler`, `product-viewer-group`,
   `g-more-link`), yet every element's tag is added (2.47M adds). The `ids` set
   is queried for a similarly small fixed set. Restricting `names`/`ids` to a
   precomputed interest set (membership-test on add) trades 2.47M unconditional
   adds for 2.47M cheap `in` checks against a small frozenset -- measure whether
   that nets out, since the `in` check isn't free either. Classes are broadly
   consulted and likely must stay full.
2. **Lexbor-side signal extraction.** Investigate whether a small number of
   targeted `css_first(...)` C probes for the gated signals beat one Python
   `css('*')` walk that materializes three sets -- i.e. revisit whether the 3a
   "presence set" is still the right shape now that the walker (not `find`
   misses) is the cost. This is the inverse of the 023 decision and must be
   re-measured, not assumed.
3. **Share one document walk.** `_get_dom_positions` (1.5 s) already walks the
   whole document with `css('*')`, and `reorder_by_dom_position._range` walks
   each main-component subtree with `css('*')` again. A single document walk that
   yields both the position map and per-component signal sets would remove
   redundant traversals -- but it couples currently-independent phases and risks
   the byte-identical contract; scope carefully and gate hard.

Recommended first step: option 1 (lowest risk, local to `_ComponentSignals`),
A/B it, then decide whether option 3's shared walk is worth the coupling.

## Lever 2: extractor hot-path review (investigate)

`ExtractorMain` (`extract_from_standard`, `get_layout`, `is_valid`,
`_ads_bottom`) is the largest phase after `make_soup` once classify is addressed,
and it grew ~648 lines since plan 023 (new layouts, kp-wholepage sub-columns,
complementary panels). It has not had a dedicated profiling pass on the
selectolax backend. Worth investigating:

- `is_valid` (1.8 s cum, 25,460 calls) runs per candidate component -- re-check
  the bad-label text scan and survey-throttler probe on lexbor nodes (the 023
  bounds were tuned for bs4).
- `extract_from_standard` / the `_StandardLayout` dispatch -- look for repeated
  `css`/`css_first` over the same subtrees across layout detection and block
  collection that could be hoisted or shared.
- `_iter_payload_blobs` (ai_overview, 2.1 s cum) -- a recent addition; confirm it
  isn't re-walking payload subtrees.

No commitment yet -- this lever is a profiling/scoping task that may or may not
surface a gateable win. Capture a `--profile-sort cumulative` split by phase
(as plan 023 did) before touching extractor code.

## Verification gate (per change)

- `uv run pytest` -- 87 snapshots green **without updates**, full suite passing.
- Back-to-back A/B of `scripts/bench_parse.py` over the fixture corpus, same
  session, clearing the noise floor; record numbers in this plan's Log.
- `ruff check` / `ruff format --check` clean.
