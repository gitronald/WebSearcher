---
id: 44
slug: shared-document-walk-signals
status: active
branch: feature/v0.10.0-shared-signal-walk
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

## Log

### 2026-06-10 — Re-grounded against the current tree at activation

Re-verified the draft's premise on HEAD (the merge of plan 041) before starting:

- **Premise intact, slightly stronger.** No commits have touched
  `classifiers/main.py` or `extractors/__init__.py` since the draft. Fresh
  profile (`python -m WebSearcher.bench --profile`, 87 SERPs x 50 iterations,
  Python 3.14.3, profile `20260611T022500Z_98b1b68`):
  `_ComponentSignals.__init__` is **15.07 s cumulative of 106.4 s total
  (~14.2%)**, tottime 12.6 s, 56,950 calls (~13.1 per SERP) — still the
  largest optimizable frame after `make_soup` (23.1 s). The draft's ~11%
  figure predates plan 040, which added two more class-gated preconditions
  (`ITWcLb` buying_guide, `gON1yc` products); both consume the full
  `classes` set, so the mechanism and the byte-identical contract are
  unchanged. `_get_dom_positions` (the existing document walk) is 4.2 s
  (~3.9%).
- **Scope correction to obstacle 3:** `ClassifyFooter.classify`
  (`classifiers/footer.py:37`) also routes into `ClassifyMain.classify`, so
  **footer** components build `_ComponentSignals` too — the shared walk must
  either cover footer roots or leave them on the per-component path, and the
  equivalence probe must cover both sections.
- **Ordering confirmed in the current tree** (`parsers.py:32-36`):
  `extract_components()` (pre-extraction position snapshot → section
  extracts → reorder) completes before any `classify_component()` call, so
  every component root is known before signals are needed — the
  "post-extraction pass keyed off known roots" approach is structurally
  available. Design hazard to respect: extraction mutates the tree (ads
  removal — the reason `_get_dom_positions` snapshots early), so the shared
  walk must be a **fresh post-extraction pass**, not a reuse of the
  pre-extraction position map.
- **Sharpened approach from the 036 finding** ("the materialization, not the
  filtering, is the real cost"): materialize the document's element list
  once post-extraction, index `mem_id -> position`, compute each root's
  subtree end via the banked `reorder._range` right-spine descent, and build
  each component's signals **lazily from a list slice** instead of a fresh
  `cmpt.css('*')` — preserving the exact per-component element sets (and the
  lazy only-when-classified scope) by construction. Whether the one extra
  document materialization beats ~13 subtree materializations per SERP is
  the empirical gate.
- **Carried in from plan 041's review:** the `_under_any` (knowledge_rhs) /
  `_parse_visual_digest` (knowledge) ancestor-walk duplication was deferred
  "to 044" — noted, but it is parser-side and a different layer than the
  classifier signal walk; **explicitly out of scope** here unless the shared
  infrastructure absorbs it for free. Keep 044 tight.
