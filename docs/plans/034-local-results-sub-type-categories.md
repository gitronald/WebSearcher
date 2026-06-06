---
status: active
branch: feature/v0.10.0-local-results-subtypes
created: 2026-05-31T23:47:41-07:00
completed:
pr: https://github.com/gitronald/WebSearcher/pull/159
---

# Replace the local_results sub_type header-slug with a closed category set

`parse_local_results()` derives `sub_type` by slugifying the component header text.
For headers that don't start with `"results for"` it falls through to
`slugify(header_lower)`, which turns query-/location-specific header text into junk,
per-query `sub_type` values that are not categories at all.

Current code (`WebSearcher/component_parsers/local_results.py:32`):

```python
sub_type = (
    "results_for" if header_lower.startswith("results for") else slugify(header_lower)
)
```

## Evidence

Observed in the `directives/crawl-5-queries-00` reparse at WebSearcher 0.9.0a2 — the
`local_results` `sub_type` column held ~141 distinct values. A handful are real
categories (`results_for` 4152, `places` 2921, `locations` 782, `businesses` 758,
`united_states` 101, `in-store_availability` 44), but the long tail is slugified
header text, one row apiece:

- `these_are_results_for__amour__de_hair_nyc|tuatara_…`
- `river_forest,_il`, `orlando,_fl`, `indianapolis,_in`
- `pints,_412_nw_5th_ave,_portland`
- `these_are_results_for__white_house_address__pennsylvania_…`

These are headers like *"These are results for amour de hair nyc | tuatara…"* or a
bare locality/address that slip past the `startswith("results for")` guard and get
slugified.

## Root cause

The header is query-dependent display text, not a category. Slugifying it into a
categorical field is the wrong shape. Plan
[016-standardize-data-models](016-standardize-data-models.md) already noticed this and
added the `startswith("results for") -> "results_for"` normalization (commits
`d76cbe7`, `3406b2b`), but that only catches one header phrasing; the `else slugify`
fallback remains. Plan
[026-selectolax-parser-backend-exploration](026-selectolax-parser-backend-exploration.md)
(`:335`) lists this same `header_lower.replace(" ", "_")` derivation among known lossy
`sub_type` derivations. The raw header is already preserved losslessly in
`details["heading"]`, so the slug carries no information that isn't kept elsewhere.

## Plan

1. Define a closed set of canonical `local_results` sub_types (the ones that recur and
   mean something): `results_for`, `places`, `locations`, `businesses`,
   `in-store_availability`, plus any others confirmed against the fixture corpus.
2. Map the header to a canonical sub_type by phrase, not by slug:
   - header containing `"results for"` (anywhere, not just prefix) -> `results_for`
   - exact/known headers (`"Places"`, `"Locations"`, `"Businesses"`, …) -> their slug
   - otherwise -> `None` (do **not** slugify free header text into a sub_type)
3. Keep storing the raw header in `details["heading"]` (already done) so nothing is
   lost when the slug is dropped.
4. Update parser snapshots / fixtures for the changed `sub_type` values.

## Notes / scope

- Breaking change to `local_results` `sub_type` values — downstream consumers
  (SearchAudits aggregation, any analysis keyed on these slugs) should expect the long
  tail of per-query slugs to collapse to a small enum plus `null`.
- Out of scope but the same antipattern: the dynamic `slugify(heading_text…)` for
  knowledge `dynamic_section` sub_types (`knowledge.py:244`), flagged in plan
  [028](028-knowledge-parsers-and-alink-reconciliation.md) (`:134`), and the
  `perspectives.py:21` header slug. Worth a follow-up pass if this approach lands well.

## Log

### 2026-06-06 — implementation

Branch `feature/v0.10.0-local-results-subtypes` (off `feature/v0.10.0`).

**Evidence re-grounded in the public fixture corpus** (carrying the lesson from
plan 040, whose Evidence counts turned out to be element-level). The 141-distinct-
values figure above is from a larger external reparse and is **not reproducible
from `tests/fixtures/serps.json.bz2`** — the public corpus is already clean. Probe
(`.claude/scratch/probe_034.py`) over the 87-SERP fixture:

| header (raw) | rows | current sub_type | new sub_type |
| --- | --- | --- | --- |
| `Results for  {Palo Alto / Austin / Portland}` | 10 | `results_for` | `results_for` |
| `Places` | 3 | `places` | `places` |
| `Locations` | 3 | `locations` | `locations` |
| `Businesses` | 3 | `businesses` | `businesses` |
| (no header — "movement") | 3 | `None` | `None` |

Every fixture header already maps to a canonical category, so on the public
corpus the change is a **no-op for sub_type values** — confirmed by the
87-snapshot suite passing unchanged. The junk long-tail the plan targets
(localities, addresses, "These are results for …") simply isn't present in the
fixtures; the fix is validated by direct unit tests instead.

**Changes:**
- `WebSearcher/component_parsers/local_results.py`: added the closed
  `_LOCAL_RESULTS_CATEGORIES` map and a pure `_header_to_sub_type()` helper.
  Header → category is matched **by phrase**: `"results for"` anywhere (not just
  as a prefix, so "These are results for …" collapses to `results_for`), known
  categories (`Places`/`Locations`/`Businesses`/`In-store availability`) → their
  slug, everything else → `None`. Removed the `else slugify(header_lower)`
  fallback (and the now-unused `slugify` import). The raw header is still kept in
  `details["heading"]` for **every** component, including unknown ones, so nothing
  is lost when no category matches.
- `WebSearcher/component_types.py`: `local_results.sub_types` updated to the
  closed set `("results_for", "places", "locations", "businesses",
  "in-store_availability")` — adds `results_for` (already emitted but previously
  undeclared) and `in-store_availability`.

**Tests** (`tests/test_local_results.py`, 13 cases): `_header_to_sub_type` over the
canonical categories + the prefix-vs-contains "results for" fix + junk localities/
addresses → `None`; a sync guard that every emittable category is a declared
sub_type; and an integration check that an unknown header drops the sub_type yet
preserves `details["heading"]`.

**Verification:** full suite `454 passed`, `87 snapshots passed` (no regression);
`ruff` clean, `pyrefly` 0 errors.
