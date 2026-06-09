---
id: 44
slug: shared-document-walk-signals
status: draft
branch:
created: 2026-06-06T14:50:43-07:00
concluded:
pr:
---

# Shared structure-aware document walk for component signals

The deferred "fuller option 3" from [plan 036](036-component-signals-and-extractor-hotpath.md).
Eliminate the per-component `_ComponentSignals` `cmpt.css('*')` walk -- the single
biggest remaining optimizable frame (~1.96 s, ~11% of parse on the 87-SERP corpus,
Python 3.14) -- by deriving the per-component signal sets from **one structure-aware
document walk** instead of N independent subtree walks.

## Plan

### Background (from plan 036)

Plan 036 banked Lever 1 (interest-set filtering of `names`/`ids`), Lever 3
(`available_on` gate), and the option-3 *safe slice* (`reorder._range` right-spine
descent). What remains is the big one:

- `_ComponentSignals.__init__` (`classifiers/main.py`) walks each main component's
  subtree via `cmpt.css('*')` to build the `classes`/`ids`/`names` sets the
  classifier chain gates on -- the largest optimizable frame after `make_soup`.
- `_get_dom_positions` (`extractors/__init__.py`) already walks the whole document
  once (`soup.css('*')`) for the reorder position map.

The bet: one document walk + cheap per-element attribution beats N full
`cmpt.css('*')` materializations (plan 036 showed the materialization, not the
filtering, is the real cost).

### Goal

Build the per-component signal sets from a single structure-aware pass that
attributes each element to its containing main-component root, folding signal-set
construction into (or alongside) the document walk -- removing the N per-component
walks.

### Key obstacles (why this is gate-hard)

1. **Ordering.** `_get_dom_positions` runs *before* extraction (to snapshot ad
   positions pre-removal), so component roots aren't known there; classification
   (which needs the signals) runs *after* extraction and reorder. So either move a
   structure-aware walk to *after* extraction, or defer signal construction to a
   post-extraction pass keyed off the known component roots.
2. **Element -> component attribution.** A flat `css('*')` iteration carries no
   depth/parent context; attributing each element to its main-component root needs
   ancestor tracking, which has its own cost.
3. **Scope mismatch.** `_ComponentSignals` is built only for components classified
   via `ClassifyMain.classify` (`type == "unknown"` at classify time); pre-typed
   components (e.g. ads) skip it. The shared walk must reproduce exactly which
   components get signal sets.
4. **Byte-identical contract.** The sets (`classes` full; `names`/`ids` filtered to
   the plan-036 interest sets) must be reproduced exactly.

### Approach (to validate, not assume)

Likely a post-extraction pass: for each main-component root, collect its subtree's
signal tokens once, stash the resulting `_ComponentSignals` on the `Component`, and
have `classify` read the stash. Whether one walk + attribution beats
N x `cmpt.css('*')` is the open empirical question -- measure it.

### Verification (gate hard -- plan 036 discipline)

- **Direct equivalence probe** (cf. plan 036's `.claude/verify_last_descendant.py`):
  for every main component on the 87-SERP corpus, assert the new
  `classes`/`ids`/`names` sets exactly equal the current `_ComponentSignals` output.
  Zero diffs required before trusting it.
- `uv run pytest` -- 87 snapshots green **without updates**, full suite passing.
- Back-to-back same-session A/B (`python -m WebSearcher.bench --profile` + timing),
  gating on the `_ComponentSignals.__init__` cum-time drop (profile is decisive;
  wall-clock is noisy on the dev box). Record in the Log.
- `ruff check` / `ruff format --check` clean.

### Abort criteria

If attribution overhead negates the saved walks (net-neutral or worse in the
profile), or byte-identical equivalence can't be guaranteed by construction, abandon
and document -- plan 036 already banked the low-risk portion.
