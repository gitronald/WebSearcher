---
status: abandoned
branch: feature/parse-pipeline-optimization
created: 2026-05-10T16:36:46+00:00
completed: 2026-05-24T10:57:35-07:00
pr:
---

# Parse Pipeline Optimization

> **Superseded by [plan 023](023-parse-pipeline-optimization-revised.md).** This
> catalogue was never implemented. A four-lens expert review (2026-05-24) found
> the priorities were set by intuition without profiling, a few items would
> silently change output, and several were already implemented or are
> measurement-noise. Plan 023 carries the corrected, profiling-first approach and
> the per-item dispositions; the detailed candidate-change catalogue below is
> retained for reference.

Reduce per-SERP parse cost without changing public API surface (`parse_serp`,
`SearchEngine`, `Extractor`, `ClassifyMain`, `ClassifyFooter`,
`FeatureExtractor`, etc.) or the result schema (`BaseResult` field set). The
existing snapshot suite (`tests/__snapshots__/`) is the regression gate — every
change below should leave `pytest` green without snapshot updates.

## Context

The hot path is:

```
parse_serp(html)
  -> utils.make_soup
  -> Extractor.extract_components
       -> _get_dom_positions (full-tree walk)
       -> rhs/header/main/footer handlers
       -> ComponentList.reorder_by_dom_position
  -> Component.classify_component (ClassifyMain chain)
  -> Component.parse_component (per-type parser)
  -> Component.add_parsed_result (Pydantic round-trip)
  -> ComponentList.export_component_results
  -> FeatureExtractor.extract_features
```

Most parse-time work is bs4 traversal, the linear classifier chain, and
per-result Pydantic validation. A handful of helpers (`filter_empty_divs`,
`get_text` on whole components, `str(soup)` re-serialization for feature
regexes) compound across components.

Alternate-language ports (e.g. selectolax/Modest) were considered and rejected:
the codebase is heavily coupled to bs4 APIs across ~30 files, and the user
constraint is "alternate languages may be considered but are not preferred".
All proposed fixes below are pure Python.

## Goals

- Preserve current functionality and backwards compatibility.
- Preserve the public API surface in `WebSearcher/__init__.py`.
- Preserve the result schema produced by `BaseResult` (field set + types).
- Pass `pytest` without snapshot updates.

## Non-goals

- No HTML parser swap (bs4 + lxml stays).
- No changes to `search_methods/` (network-bound, already excluded from
  coverage in `pyproject.toml`).
- No new dependencies.

## Module-by-module changes

### 1. `WebSearcher/extractors/__init__.py`

#### 1a. `_get_dom_positions` — single-pass DFS

**Current:** `extractors/__init__.py:33-49` does `soup.find_all(True)` (one
full tree walk) and then a second pass walking the list in reverse to
propagate `end` indices via `parent` lookups. For a real SERP this is ~5–10k
tags and two parallel lists plus a dict.

**Proposed:** Replace with a single recursive pre/post DFS that records
`(start, end)` per tag in one pass, removing the second pass and `parent`
probes:

```python
@staticmethod
def _get_dom_positions(soup):
    positions = {}
    counter = [0]

    def walk(tag):
        start = counter[0]
        counter[0] += 1
        for child in tag.children:
            if getattr(child, "name", None):
                walk(child)
        positions[id(tag)] = (start, counter[0] - 1)

    for child in soup.children:
        if getattr(child, "name", None):
            walk(child)
    return positions
```

Output shape (`{id(tag): (start, end)}`) is identical, so
`reorder_by_dom_position` does not need to change for this item.

#### 1b. Skip reorder when not needed

**Current:** `extract_components` always calls
`components.reorder_by_dom_position(dom_positions)`.

**Proposed:** When `len(main_components) <= 1` there is nothing to reorder;
skip the call and the dom-position dict construction entirely. Detect this
before building `dom_positions`.

### 2. `WebSearcher/components.py`

#### 2a. `reorder_by_dom_position` is O(n²)

**Current:** `components.py:174-201`. `_effective_pos` iterates over all
`main_components` for each main component to detect ancestor ranges. With M
main components this is O(M²) before the per-ancestor child scan.

**Proposed:** Sort `main_components` once by `dom_positions[id(elem)][0]` and
walk in start order with a stack of open ranges:

- Push current range onto the stack.
- Pop entries whose `end < current.start` before each push.
- The top of the stack after pops is the immediate ancestor (if any).

Only run the existing "first child after nested subtree" fixup for the
ancestor case (rare). Net cost drops from O(M²) to O(M log M + ancestor
fixups). DOM order, ancestor detection semantics, and rank assignment remain
identical — only the algorithm changes.

#### 2b. Per-result Pydantic round-trip — **largest single win**

**Current:** `components.py:130-133` validates every parsed result via
`BaseResult(**parsed_result).model_dump()`. This runs once per subresult on
every SERP (often 30–100+ per parse). Validate→dump round-trip is the largest
measurable hot-spot per SERP after bs4 traversal.

**Proposed:** All result dicts are produced by parsers we control, so full
validation here is mostly defensive. Two compatible options (pick whichever
the maintainer prefers — both produce byte-identical output):

1. `model_construct`:

   ```python
   def add_parsed_result(self, parsed_result):
       result = BaseResult.model_construct(**parsed_result).model_dump()
       self.result_list.append(result)
   ```

   Skips field validation but still applies field defaults via the
   constructed model.

2. Cached defaults + dict merge:

   ```python
   _BASE_RESULT_DEFAULTS = {
       name: field.default for name, field in BaseResult.model_fields.items()
   }

   def add_parsed_result(self, parsed_result):
       self.result_list.append({**_BASE_RESULT_DEFAULTS, **parsed_result})
   ```

   No Pydantic call at all. Equivalent output for current parsers. Falls
   back to full validation only when an unexpected key/type is detected
   (optional safety net).

Both leave the resulting dict's keys/values identical to today's output.

#### 2c. `export_component_results` builds metadata dict per result

**Current:** `components.py:214-222` does `{**result_metadata, **result}` per
result.

**Proposed:** Merge the `serp_rank` assignment into the same pass and avoid
re-creating `result_metadata` per result. Trivial; only worth doing
alongside 2b.

### 3. `WebSearcher/classifiers/main.py`

#### 3a. Pre-screen via element attrs / inner tag flags

**Current:** `ClassifyMain.classify` (`classifiers/main.py:60-95`) walks ~22
classifiers in order, each running 1–4 `cmpt.find(...)` probes. Worst case is
~66 bs4 finds per component before parsing even starts.

**Proposed:** Build a one-pass attribute index for the component's root
element and a presence map for cheap inner tag names that drive multiple
branches:

- Root attrs: `class` (set), `id`, `role`, `jscontroller`, `data-attrid`,
  `data-hveid`, `aria-label`.
- Inner tag presence flags: `g-scrolling-carousel`, `block-component`,
  `g-card`, `h2`, `g-tray-header`, `g-review-stars`,
  `gls-profile-entrypoint`.

Each existing classifier registers a precondition predicate against this
index. Only run the slower `find()`-based check when the precondition is
true. Plain `class="g"` general results collapse to a couple of dict
lookups. The classifier order, the set of classifiers, and their match
semantics stay the same — preconditions can only short-circuit a known-miss.

#### 3b. Cache header-text dispatch tables and selectors

**Current:** `ClassifyMainHeader._classify_header` (`classifiers/main.py:24-42`)
rebuilds `selectors` and calls `header_text_to_type(level)` per invocation.
`header_text_to_type` rebuilds an inverted dict from `COMPONENT_TYPES` each
call.

**Proposed:**

- Memoize `header_text_to_type(level)` (e.g. `functools.lru_cache`) — pure
  function over an immutable tuple, output is identical.
- Hoist the `selectors` list to a module-level constant per `level`.

Pure refactor; output unchanged.

#### 3c. `knowledge_box` materializes all stripped strings

**Current:** `classifiers/main.py:210` does
`text_list = list(cmpt.stripped_strings)` to read `text_list[0]`. Walks the
entire subtree.

**Proposed:**

```python
first_text = next(iter(cmpt.stripped_strings), None)
if first_text == "COVID-19 alert":
    condition["covid_alert"] = True
```

#### 3d. `available_on` runs `get_text` on the whole component

**Current:** `classifiers/main.py:106` calls `utils.get_text(cmpt)` to
substring-search `"/Available on"`. For a multi-KB component this is a full
text traversal, even though `available_on` rarely matches.

**Proposed:** Tighten the precondition to a structural probe (e.g. the
specific link/badge tag carrying the "Available on" label) before falling
back to a text scan. Output unchanged for matching cases.

### 4. `WebSearcher/utils.py`

#### 4a. `filter_empty_divs` calls `.text` per candidate

**Current:** `utils.py:209-217`. `.text` walks the subtree to build a string
just to test `.strip() != ""`. Hot because `find_all_divs(filter_empty=True)`
is the default for many helpers.

**Proposed:** Early-terminating non-empty test:

```python
def filter_empty_divs(divs):
    out = []
    for c in divs:
        if not c:
            continue
        # Walk strings lazily; bail at the first non-blank.
        for s in c.strings if hasattr(c, "strings") else (str(c),):
            if s and s.strip():
                out.append(c)
                break
    return out
```

Functionally equivalent; cost drops from "build full text" to "find first
non-blank string".

#### 4b. `find_all_divs` rebuilds `attrs` dict

**Current:** `utils.py:204` calls `dict(attrs)` even when `attrs` is already
a `dict`.

**Proposed:** `attrs if isinstance(attrs, dict) else dict(attrs)`. Trivial.

#### 4c. `get_domain` LRU cache + eager tldextract

**Current:** `utils.py:251-262` calls `tldextract.extract(url)` per URL.
tldextract caches internally, but `get_domain` itself reconstructs strings
each time and is called on every result URL. URLs repeat across results
within a SERP (same shopping-ad domain across cards, etc.).

**Proposed:**

- Wrap `get_domain` with `functools.lru_cache(maxsize=4096)`.
- Module-level `tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)`
  to skip the lazy first-call fork in long-running services.

Output unchanged.

### 5. `WebSearcher/feature_extractor.py`

**Current:** `FeatureExtractor.extract_features` (`feature_extractor.py:21-23`)
does `html = str(soup)` when handed a `BeautifulSoup`, then runs four regexes
over the serialized HTML. **`parse_serp` always passes a soup**, so this
serialization runs on every parse — multi-millisecond on a 1MB SERP.

**Proposed:** When the input is a `BeautifulSoup`, replace each regex probe
with a structural lookup that produces the same value:

- `result-stats`: `soup.find("div", {"id": "result-stats"})` and parse its
  text for the count and time strings.
- `<html lang>`: `soup.html.get("lang")` if `soup.html` else `None`.
- "did not match any documents" notice: detect via the known notice div
  (id/class) instead of regex over full HTML. Confirm the matching div on
  fixtures before swapping.
- Three fixed-string flags (`notice_shortened_query`,
  `notice_server_error`, `infinity_scroll`): structural lookups
  (e.g. `soup.find("span", {"class": "RVQdVd"})` for `infinity_scroll`).

Keep the regex path for the raw-HTML input branch (no soup yet → regex is
appropriate). Output (`SERPFeatures` instance) is identical in both cases —
verify via `test_feature_extractor.py`.

### 6. `WebSearcher/component_parsers/`

Per-call recompilation and redundant traversals scattered across parsers.

#### 6a. `general.py` — recompiled regexes per call

**Current:** `component_parsers/general.py:145, 147, 154` re-compile
`re.compile("fG8Fp")` per call. `parse_ratings` (`general.py:170, 177`)
re-compiles `r"^\d*[.]?\d*$"` and `r" vote[s]?| review[s]?"` per call.

**Proposed:** Hoist all `re.compile(...)` calls to module-level constants.
(`re` does cache compiled patterns, but only up to 512 entries with hashing
overhead — module-level constants are faster and clearer.)

#### 6b. `general.py` — duplicate `find` for nested `.g` dedup

**Current:** `find_subcomponents` (`general.py:23-32`) calls `find_all("div",
{"class": "g"})` then `find("div", {"class": "g"})` — the first result is
already the same first hit.

**Proposed:**

```python
subs = cmpt.find_all("div", {"class": "g"})
if subs:
    parent_g = subs[0]
    if parent_g.find("div", {"class": "g"}):
        return [parent_g]
    return subs
```

#### 6c. `ads.py` — `find_all` for existence tests

**Current:** `component_parsers/ads.py:31-36`. `classify_ad_type` uses
`utils.find_all_divs` (which materializes a list and runs `.text` on every
candidate via `filter_empty=True`) when it only needs existence.

**Proposed:** Replace with `cmpt.find(sel.name, attrs=sel.attrs)`,
returning at first hit. Identical classification result.

#### 6d. `notices.py` — pointless `copy.copy(cmpt)`

**Current:** `component_parsers/notices.py:85` does `cmpt = copy.copy(cmpt)`.
`copy.copy` on a bs4 Tag is a *shallow* copy: children still reference the
original tree, so the subsequent `extract()` mutates the source anyway.
Behaviorally fine because `parse_serp` is fire-and-forget on the soup, but
the `copy.copy` is wasted allocation.

**Proposed:** Drop the `copy.copy` call. Verify under the existing snapshot
tests; remove if green.

#### 6e. `knowledge.py` — repeated `cmpt.find("h2")`

**Current:** `component_parsers/knowledge.py:48-114` re-runs
`cmpt.find("h2")` six times across an `elif` chain.

**Proposed:** Compute once at the top:

```python
h2 = cmpt.find("h2")
h2_text = h2.text if h2 else None
```

and dispatch on `h2_text`. Same branches, same outputs.

#### 6f. `top_stories.py` — sequential `find_all` for disjoint classes

**Current:** `component_parsers/top_stories.py:32-35` runs four
`find_all_divs` plus `find_children` for five disjoint class names. With
`filter_empty=True` each one walks subtrees.

**Proposed:** Single `cmpt.find_all("div", attrs={"class": [...]})` plus
the `g-inner-card` lookup, then dispatch by which class matched. Concatenated
output is the same; the order of `divs` must be preserved.

### 7. `WebSearcher/logger.py` and callers

**Current:** Many `log.debug(f"...")` calls in inner loops
(`extractors/extractor_main.py`, `classifiers/main.py`, etc.). The f-string
materializes regardless of level.

**Proposed:** Use lazy `%`-style formatting:

```python
log.debug("main_layout: %s", layout_label)
```

or guard with `if log.isEnabledFor(logging.DEBUG)` for multi-arg messages.
Pure refactor; no functional change.

### 8. `WebSearcher/__init__.py`

**Current:** `from .searchers import SearchEngine` pulls in
`selenium_searcher.py` → `undetected_chromedriver` on every package import,
even for parse-only consumers. Cold import is hundreds of milliseconds.

**Proposed:** Lazy-load `SearchEngine` via PEP 562 `__getattr__`:

```python
__all__ = [..., "SearchEngine", ...]

def __getattr__(name):
    if name == "SearchEngine":
        from .searchers import SearchEngine as _SE
        return _SE
    raise AttributeError(name)
```

`WebSearcher.SearchEngine` still resolves; `from WebSearcher import
SearchEngine` still works. Parse-only consumers skip the Selenium import.

### 9. Out of scope (explicitly skipped)

- **Alternate HTML parser** (`selectolax`/Modest): would break ~30 files
  worth of bs4 API usage and the public `make_soup`/`load_soup` return type.
  Skip per the user constraint.
- **`search_methods/`**: dominated by network and Selenium init; already
  excluded from coverage in `pyproject.toml`. Out of scope here.
- **Concurrency for `parse_serp`**: caller responsibility; no API change
  warranted.

## Suggested rollout order (ROI vs. risk)

1. **2b** — Pydantic round-trip removal. Largest single win, low risk via
   `model_construct` route.
2. **5** — `FeatureExtractor` `str(soup)` removal. Eliminates a guaranteed
   full-document serialize on every parse.
3. **2a** — `reorder_by_dom_position` O(n²) → O(n log n). Measurable on
   SERPs with many main components.
4. **3a / 3b** — Classifier dispatch + cached selectors. Speeds every SERP
   proportional to component count.
5. **4a** — `filter_empty_divs` early termination. Touches many helpers;
   benchmark before/after to confirm.
6. **6a–6f** — Parser micro-fixes. Small, easily tested with the snapshot
   suite.
7. **8** — Lazy `SearchEngine` import. Improves cold-start for parse-only
   consumers.
8. **1a / 1b** — Single-pass DFS + skip-when-unneeded. Cleanup pass after
   2a lands.
9. **3c / 3d, 4b, 4c, 7** — Final polish.

## Files modified

| File | Change |
|------|--------|
| `WebSearcher/extractors/__init__.py` | 1a single-pass DFS; 1b skip when unneeded |
| `WebSearcher/components.py` | 2a stack-based reorder; 2b skip Pydantic round-trip; 2c merge metadata |
| `WebSearcher/classifiers/main.py` | 3a attr/tag pre-screen; 3b cache header dispatch + selectors; 3c `next(iter(...))`; 3d tighten `available_on` |
| `WebSearcher/utils.py` | 4a `filter_empty_divs` early terminate; 4b `attrs` dict reuse; 4c `get_domain` lru_cache + eager TLDExtract |
| `WebSearcher/feature_extractor.py` | 5 structural probes for soup input |
| `WebSearcher/component_parsers/general.py` | 6a hoist regexes; 6b reuse first `.g` find |
| `WebSearcher/component_parsers/ads.py` | 6c `find` instead of `find_all_divs` for existence |
| `WebSearcher/component_parsers/notices.py` | 6d drop `copy.copy` |
| `WebSearcher/component_parsers/knowledge.py` | 6e compute `h2`/`h2_text` once |
| `WebSearcher/component_parsers/top_stories.py` | 6f single `find_all` with class list |
| Multiple modules | 7 lazy `%`-formatted debug logs |
| `WebSearcher/__init__.py` | 8 lazy `SearchEngine` import |

## Verification

For each change, the gate is:

- `pytest` — the snapshot suite under `tests/__snapshots__/` covers
  `parse_serp` end-to-end on real fixtures in `tests/fixtures/`. Every change
  above should leave the suite green without snapshot updates.
- `python -c "import WebSearcher; WebSearcher.parse_serp; WebSearcher.SearchEngine"`
  — confirms the public API still resolves (including the lazy
  `SearchEngine` from item 8).
- A small benchmark harness (suggested as `scripts/bench_parse.py`) timing
  `parse_serp` over the fixture set, run before/after each batch of changes.
  Not landed as a test (timings are environment-dependent), but kept around
  for ad-hoc measurement.

## Why this is safe

- No public API names or signatures change.
- `BaseResult` field set is unchanged; result dicts keep identical keys and
  value types.
- `SERPFeatures` field set is unchanged.
- Component classification semantics are unchanged — preconditions in 3a can
  only short-circuit known misses, not change a match.
- Snapshot tests pin end-to-end behavior across the full fixture set; any
  regression surfaces immediately.
