---
status: active
branch: feature/parse-pipeline-optimization
created: 2026-05-24T10:57:35-07:00
completed:
pr:
---

# Parse Pipeline Optimization (Profiling-First Revision)

Supersedes [plan 017](017-parse-pipeline-optimization.md). Plan 017 catalogued a
set of `parse_serp` micro-optimizations but was never implemented. A four-lens
expert review (behavior-preservation, codebase fact-check, performance/ROI, and
Python-internals) found that the catalogue is sound in spirit but (a) ranks items
by intuition with no profiling evidence, (b) contains a few changes that would
silently alter output and break the snapshot suite, (c) lists several items that
are already implemented or are measurement-noise, and (d) cites line numbers and a
classifier inventory that have since drifted.

This plan keeps 017 as the detailed catalogue of candidate changes and records
**what to do differently**: profile first, reorder by evidence, fix the
correctness traps, drop the dead/noise items, and refresh the stale references.
The goal, constraints, non-goals, and "why this is safe" framing from 017 still
hold: no public API or `BaseResult`/`SERPFeatures` schema changes, and `uv run
pytest` must stay green **without snapshot updates**.

## 1. Methodology change: profile before optimizing (prerequisite)

017 names item 2b (Pydantic round-trip) "the largest single win" and item 5
(`str(soup)`) a "guaranteed cost" with no measurement, and defers the benchmark
harness to an optional afterthought. Invert this.

First deliverable, before touching any hot-path code:

- Add `scripts/bench_parse.py` (committed). Load a fixed corpus from the stored
  fixtures and parse each SERP N times, reporting per-SERP **median + median
  absolute deviation** (parse times are right-skewed; mean is misleading). Run
  with logging at WARNING so item-7-style effects don't contaminate timings.
  Corpus = the bz2 fixtures already in the repo:
  ```bash
  uv run python scripts/bench_parse.py \
      --fixtures tests/fixtures/serps-v0.6.7.json.bz2 \
                 tests/fixtures/serps-v0.6.8.json.bz2 \
      --iterations 200 --runs 5
  ```
- Capture a `cProfile` baseline (cumulative + tottime) and a `py-spy` sampling
  flamegraph over the same corpus to cross-check (cProfile over-weights
  many-small-call paths like bs4). Record the top line items
  (`make_soup` vs `_get_dom_positions` vs `ClassifyMain.classify` vs per-parser
  `find_all` vs `str(soup)` vs `BaseResult(...)`) in this plan's Log.

Gate every subsequent item on a measured delta that clears noise (target: >=3% of
total parse time or >=2x the run-to-run MAD). Items that don't clear it are merged
as readability/cleanup, not claimed as speedups.

## 2. Revised rollout order

Derived from the review, to be re-confirmed against the baseline profile:

1. **017 item 5** -- `str(soup)` removal in `feature_extractor.py`. Highest-confidence
   real win (unconditional full-document re-serialize on every parse). **Not a pure
   refactor** -- see guardrails below.
2. **Profiling baseline** (section 1) -- prerequisite for everything after this.
3. **017 item 3a (root-attr preconditions only)** -- if the profile confirms the
   classifier chain is hot. Drop the inner-tag-presence-map half (see section 4).
4. **017 item 2a** -- `reorder_by_dom_position` O(M^2) -> O(M log M). Real but small
   (M is typically 10-30); confirm on many-component SERPs.
5. **017 item 4a** -- `filter_empty_divs` early termination. Broad small win across
   helpers; gate on measurement.
6. **017 item 2b** -- Pydantic round-trip. **Demoted from #1.** `BaseResult` is a
   flat 9-field model validated in Rust; likely microseconds. Implement only if the
   profile justifies it, and only via `model_construct` (see guardrails).
7. **017 item 8** -- lazy `SearchEngine` import. Real (~65 ms) but it is
   **cold-start/import time, not per-parse**; label it as such, keep it.
8. **017 items 4b, 4c, 6b, 6c, 6f** -- remaining micro-fixes, each gated and
   verified individually.

## 3. Per-item disposition

| 017 item | Disposition | Reason |
|---|---|---|
| 1a single-pass DFS | **DROP as perf** (profiled ~1%) | Constant-factor win on the same full walk; low risk. Optional readability only. |
| 1b skip reorder when <=1 main cmpt | **DROP as perf** (profiled ~1%) | Component count is only known *after* extraction -- the skip must be placed after the `extract()` calls, not before `dom_positions` is built. |
| 2a stack-based reorder | **DROP as perf** (reorder ~0%) | Must reproduce the "first child after nested subtree" ancestor fixup exactly; verify `cmpt_rank` on a fixture where one component nests another. |
| 2b Pydantic round-trip | **DROP as perf** (profiled 0.1%) | See guardrails; cached-defaults variant rejected. |
| 2c metadata merge | Keep | Trivial; do alongside 2b. |
| 3a classifier pre-screen | **Revise** | Keep cheap root-attr/class preconditions; **drop the inner-tag presence map** (its construction traversal likely cancels the `find()` savings). Index must also cover the new `ai_overview` and `knowledge_subcard` classifiers. |
| 3b cache header dispatch | Keep, **retarget** | `header_text_to_type` now lives in `WebSearcher/component_types.py`, not `classifiers/main.py`. Apply `lru_cache` there; do not mutate the returned dict. |
| 3c `next(iter(...))` in knowledge_box | Keep | Now at `classifiers/main.py:222`. |
| 3d tighten `available_on` | **Mostly done** | Fast heading-span probe already added; only the residual `utils.get_text` fallback (`classifiers/main.py:111`) remains to tighten. |
| 4a filter_empty_divs early-terminate | Keep, verify | Confirm `.strings` vs `.text` emptiness verdict on whitespace/comment-only divs. |
| 4b reuse attrs dict | Keep | Trivial. |
| 4c get_domain lru_cache + eager TLDExtract | Keep, **document behavior change** | `suffix_list_urls=()` pins to the bundled PSL snapshot (no network refresh) -- not a strict no-op. Fine for Google domains; state it. |
| 5 structural feature probes | Keep, **promote, verify per-field** | See guardrails; scope is now ~6 features and `overlay_precise_location` is already structural. |
| 6a hoist regexes | **Drop as perf** | `re` already caches; `_ARIA_*` patterns already hoisted. Keep only as readability. |
| 6b reuse first `.g` find | Keep | Redundant `cmpt.find` still present at `general.py:24`. |
| 6c `find` for existence | Keep, **widen** | Applies to both `classify_ad_type` and `parse_ads` (`ads.py:58`), not just the former. |
| 6d drop `copy.copy` | Keep, verify | Confirm the extracted notice subtree doesn't overlap another component. |
| 6e compute `h2` once | **Already done** -- skip | `knowledge.py:43-44` already computes `h2`/`h2_text` once. |
| 6f single find_all in top_stories | **Revise** | A single class-list `find_all` returns global document order and interleaves previously class-grouped cards -> changes `sub_rank`. The parser now has 6 collection passes (two conditional fallbacks). Only consolidate where document order is provably unchanged. |
| 7 lazy `%`-logging | **Drop as perf** | DEBUG-only. Real trap: `%s` drops `:,` thousands separators (e.g. `extractors/__init__.py:31`). Use `if log.isEnabledFor(logging.DEBUG):` guards on the `:,`/multi-arg lines instead of mechanical conversion. |
| 8 lazy SearchEngine import | Keep, **complete it** | See guardrails. |

## 4. Correctness guardrails (must not break snapshots)

- **2b -- `model_construct` only, and watch extra keys.** The error-result dict at
  `components.py:117-124` carries `cmpt_rank`, which is *not* a `BaseResult` field.
  Today `BaseResult(**d)` drops it (`extra="ignore"`); `model_construct` would pass
  it through into `model_dump()` and change output for any errored SERP. Strip
  non-model keys before constructing, or keep validation on the error path.
  Reject the cached-`field.default` dict-merge variant entirely: it leaks extra
  keys *and* emits a `PydanticUndefined` sentinel for any future `default_factory`
  field. Neither shortcut coerces types (e.g. `"5"` -> `5`); this is safe only
  while every parser already emits correctly typed values -- assert this with the
  snapshot suite.
- **5 -- verify each structural probe per field on fixtures.** The current
  `result-stats` regex is non-DOTALL over `str(soup)` and can disagree with
  `soup.find("div", {"id": "result-stats"})`. Diff `result_estimate_count` /
  `result_estimate_time` and every other migrated feature over the fixture corpus
  before swapping; keep the regex path for the raw-HTML input branch.
- **1b -- place the skip after extraction**, since main-component count is zero
  before the `extract()` calls run.
- **6f -- preserve document order**; do not let a consolidated `find_all` reorder
  cards relative to the current per-class grouping.

## 5. Stale references to refresh while implementing

The review confirmed these drifted since 017 was written (2026-05-10):

- Classifier chain is now **24 classifiers**, with `ai_overview` and
  `knowledge_subcard` added -- 3a's precondition index must cover their triggers.
- `header_text_to_type` moved to `WebSearcher/component_types.py`.
- Line numbers shifted: `reorder_by_dom_position` starts at `components.py:161`;
  `knowledge_box`'s string materialization at `classifiers/main.py:222`;
  `get_domain` at `utils.py:245-256`; `copy.copy` at `notices.py:92`.
- `feature_extractor.extract_features` now covers ~6 features and already uses a
  structural lookup for `overlay_precise_location`.

## 6. Missing opportunities to investigate (post-profile)

The review flagged these as larger structural levers that 017 did not consider;
evaluate them against the baseline profile before committing to the micro-fixes:

- **Single per-component scan feeding both classify and parse.** Each component is
  walked by the classifier chain and then re-walked by its type parser, often for
  the same elements. A shared structural scan directly attacks the bs4-traversal
  cost that 017 itself names as dominant.
- **`SoupStrainer` / parse-once-narrower** in `make_soup` to shrink the tree (and
  every downstream `find_all`, `_get_dom_positions`, and serialization) without
  swapping the parser backend.
- **Measure `make_soup` itself** -- lxml parsing of a ~1 MB document is often the
  single largest line in a parse profile and is currently treated as a fixed cost.

## 7. Item 8 completion details

Lazy `SearchEngine` is correct but the 017 snippet is incomplete:

- **Delete** the eager `from .searchers import SearchEngine` in
  `WebSearcher/__init__.py` (otherwise `__getattr__` is dead code).
- Keep `SearchEngine` in `__all__` (preserves the public contract and the
  real-names-in-`__all__` rule; star-imports will still trigger the heavy import,
  which is acceptable).
- Add a module-level `def __dir__(): return __all__` so introspection/IDEs still
  surface `SearchEngine` (PEP 562 names are invisible to the default `dir()`).
- Cache the resolved attribute on the module (`globals()[name] = _SE`) so repeated
  access skips `__getattr__`.

Confirmed import chain: `__init__.py` -> `.searchers` -> `selenium_searcher` ->
`undetected_chromedriver` (+ selenium, websockets), ~65 ms, paid by every
`import WebSearcher.*` including parse-only consumers.

## 8. Verification

Per change, the gate is:

- `uv run pytest` -- snapshot suite must stay green without snapshot updates.
- `uv run python -c "import WebSearcher; WebSearcher.parse_serp; WebSearcher.SearchEngine"`
  -- public API (incl. the lazy `SearchEngine`) still resolves.
- A before/after run of `scripts/bench_parse.py` over the fixture corpus showing
  the item clears the noise threshold; record numbers in the Log.

## Log

### 2026-05-24 -- profiling baseline (section 1 deliverable)

Added `scripts/bench_parse.py`: loads the full fixture corpus into memory first
(decompression/JSON load excluded from the clock -- only `ws.parse_serp(html)` is
timed), pauses gc during timing, sets the `WebSearcher` logger to WARNING, warms
up untimed, and reports per-SERP median + MAD plus inter-run spread.

Corpus: 66 SERPs (10 v0.6.7, 52 v0.6.8, 2 ads, 1 jobs, 1 knowledge-subcards).
Machine: WSL2 (timer jitter is real here).

**Timing** (`--iterations 8 --runs 3`):
- median **134 ms/SERP**, MAD 41 ms; min 42, p90 242, max 338 ms.
- corpus ~10.3 s/pass; inter-run MAD 127 ms.
- **noise floor ~2.5%** (2x inter-run MAD) -- the gate every change must clear.

**cProfile** (`--profile`, 198 parses, 135 s total, sorted by tottime):

| Bucket | Key frame | cumtime | ~share | Implication |
|---|---|---|---|---|
| bs4 find/filter traversal | `filter.py:130(filter)` | 80.1 s | ~59% | Dominant cost. Real prize = item 3a preconditions + the missing "single per-component scan feeding classify+parse" (double traversal). |
| HTML serialization `str(soup)` | `element.py:2570(decode)` | 25.0 s | ~18.5% | 273 calls (~1.4/parse). Confirms **item 5 as #1** -- biggest easily-removable chunk. |
| lxml parse (`make_soup`) | `_lxml.py:488(feed)` | 21.6 s | ~16% | Structural; evaluate `SoupStrainer` (section 6). |
| Pydantic round-trip (item 2b) | -- | -- | not in top 30 | Negligible -- confirms demotion; implement only if a later profile changes. |

Conclusion: revised rollout order holds. Proceed with item 5 first, then attack
bs4 traversal (3a + double-traversal), then weigh a `SoupStrainer` for `make_soup`.
Drop 2b as a perf item.

### 2026-05-24 -- item 5: structural feature probes (str(soup) removal)

First moved `feature_extractor.py` -> `extractors/extractor_serp_features.py` (the
class name `FeatureExtractor` is unchanged; only the module path moved). Then split
extraction into two paths:

- **Raw-HTML path** (`_extract_from_html`): regex over the original markup,
  byte-for-byte unchanged -- there is no `str(soup)` cost when the input is already
  a string, so the historical behavior is preserved exactly (plan section 3).
- **Soup path** (`_extract_from_soup`): structural lookups that never serialize the
  whole document. Each probe is scoped to the smallest element so output is
  byte-identical to the old regex-over-`str(soup)`:
  - result-stats: `soup.find("div", {"id": "result-stats"})`, then the *same*
    `RX_RESULT_STATS` regex applied to `str(stats_div)` (a div is serialized
    identically whole-tree or alone, and the id is unique).
  - language: `soup.find("html").get("lang")`.
  - three text notices: a single `soup.get_text()` pass (replaces three scans of
    `str(soup)`).
  - infinity_scroll: `any(SPAN in str(span) for span in find_all("span", class RVQdVd))`
    -- serializes only candidate spans, preserving the old exact-substring semantics
    (extra attributes still break the match).
  - overlay/captcha were already structural.

**Verification:** all 66 snapshots green without updates (byte-identical features
across the corpus), plus 7 new soup-path parity unit tests in
`test_extractor_serp_features.py`.

**Benchmark** (`--iterations 8 --runs 3`, same machine):

| Metric | Baseline | After item 5 | Delta |
|---|---|---|---|
| Per-SERP median | 134.2 ms | 111.2 ms | -17.1% |
| Corpus total | 10269 ms | 7559 ms | -26.4% |

Well above the ~2.5% noise floor. Corpus-total gain exceeds the per-SERP median
because large SERPs (where serialization dominated) benefit most -- consistent with
the ~18.5% serialization share measured in the baseline profile.

### 2026-05-24 -- classify-vs-parse profiling (decision point)

Cumulative-sorted profile (post item 5) to split the bs4 cost by phase. Phase
cumtime as a share of `parse_serp` total:

| Phase | % total | Note |
|---|---|---|
| `ExtractorMain.extract` (extraction) | **22.5%** | unplanned -- biggest single phase |
| `parse_component` (parse) | 21.2% | |
| `classify_component` (classify) | 20.9% | item 3a target |
| `make_soup` (lxml) | 18.0% | structural |
| `extract_features` | 3.5% | down from ~18% pre-item-5 |
| `_get_dom_positions` + `reorder_by_dom_position` (1a/1b/2a) | **~1%** | noise |
| `add_parsed_result` / pydantic (2b) | **0.1%** | noise |

The universal cost is bs4 `find`/`find_all` volume: ~1290 calls per parse (255k over
198 parses) funneling into `matches_tag` (44.5 s) and `_attribute_match` (20.5 s).

**Decisions:**
- **Drop 1a, 1b, 2a, and 2b as performance items** -- measured at ~1% and 0.1%, below
  the noise floor. (1a/1b/2a may still be worth doing as readability, but not for speed.)
- **Do item 3a next**: classify is 20.9% and find-dominated; cheap root-attr
  preconditions replace subtree-walking `find()` probes with dict lookups. The
  precondition index is also a stepping stone to the double-traversal win.
- `make_soup` (18%) via `SoupStrainer` is likely **unsafe** -- the parser navigates
  ancestors/siblings/full subtrees, which a strainer would prune. Deprioritize.
- Biggest follow-on prize after 3a: the double-traversal between classify and parse
  (~42% combined), plus targeted `ExtractorMain.extract` hot spots (`is_valid` calls
  `c.text` and `c.find` per candidate component).

### 2026-05-24 -- item 3a: classifier signal preconditions

Added `_ComponentSignals` (one `descendants` walk -> sets of class names, ids, and
tag names) and converted `ClassifyMain.classify` to a `(classifier, precondition)`
chain. 14 of the 24 classifiers are gated on a **necessary** structural signal
(e.g. top_stories needs `g-scrolling-carousel`, videos needs one of the VibNM-family
classes, local_results needs Qq3Lb/VkpGBb); when the signal is absent the classifier
is skipped without a full-subtree `find()`. The 10 text/heading/root-class
classifiers (locations, header, available_on, knowledge_panel, twitter, flights,
general, people_also_ask, knowledge_box) always run -- general results trigger them
anyway, so a signal gate would not skip them. Dropped the inner-tag *presence map*
idea from 017; this is the lighter "necessary signal" form.

Because each precondition is a necessary condition, a skip can only short-circuit a
guaranteed miss -- classification is unchanged.

**Verification:** 66 snapshots green without updates (byte-identical classification),
130 tests pass.

**Benchmark:** the first run was discarded (inter-run spread 4.4 s from external
machine load -- MAD/spread ~20x the clean floor). Clean re-run (`--iterations 8
--runs 4`, spread 85 ms):

| Metric | After item 5 | After item 3a | Delta |
|---|---|---|---|
| Per-SERP median | 111.2 ms | 104.4 ms | -6.1% |
| Corpus total | 7559 ms | 7096 ms | -6.1% |

Above the noise floor. Cumulative from baseline: corpus -30.9%, per-SERP median
-22.2%. The reviewer's net-neutral worry did not materialize: classify is
miss-dominated (each `find()` miss is a full subtree walk), so one signal walk plus
set lookups beats ~14 miss-walks per component.
