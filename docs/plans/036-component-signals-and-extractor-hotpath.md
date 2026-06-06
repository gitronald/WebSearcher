---
status: done
branch: feature/v0.10.0-component-signals-hotpath
created: 2026-06-01T13:35:50Z
completed: 2026-06-06T14:51:25-07:00
pr: https://github.com/gitronald/WebSearcher/pull/157
---

# `_ComponentSignals` consolidation + extractor hot-path review

Follow-up to [plan 035](035-get-text-native-fastpath.md). With the `get_text`
native fast path banked (~7% off `parse_serp`), the profile's #2 *optimizable*
cost is now `classifiers/main.py:_ComponentSignals.__init__` (Lever 1); the
extractor phase is the largest unprofiled-in-detail bucket worth a pass
(Lever 2); and `get_text`-caller attribution surfaced the `available_on`
classifier's full-component text fallback as the single most expensive
`get_text` caller (Lever 3). This plan scopes all three. Same methodology as
plans 023/035: per-SERP median + MAD, gate on the
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

## Lever 3: the `available_on` classifier full-component `get_text`

`get_text`-caller attribution (`pstats.print_callers`, 435 parses) shows the
single most *expensive* `get_text` caller is not a parser but the
`ClassifyMain.available_on` classifier (`classifiers/main.py:162`): **4,320 calls,
0.649 s cumtime** -- the highest of any caller. (For contrast, the entire
`local_results`/`locations` family is ~1-3% of `get_text` calls; the dominant
*volume* is `parse_general_result` ~10.5k and the knowledge genexpr ~9k, but
those are scoped to small nodes. `available_on` is expensive per-call, not
high-count.)

The cost is structural to how the classifier is written:

```python
def available_on(cmpt) -> str:
    for heading in cmpt.css("span.mgAbYb"):           # cheap, scoped
        if (get_text(heading, strip=True) or "") == "Available on":
            return "available_on"
    text = get_text(cmpt) or ""                        # WHOLE-component walk
    return "available_on" if "/Available on" in text else "unknown"
```

`available_on` sits in the chain with **precondition `None`**, so it runs for
every component that reaches it (most do -- it is before `knowledge_panel`,
`general`, etc.), and the fallback `get_text(cmpt)` materializes the entire
component's text just to substring-test `"/Available on"`. That is a full-subtree
text walk on the majority of components, every parse.

Directions (each byte-identical, pinned by the 87-snapshot suite):

1. **Gate it on a necessary structural signal.** Find what markup actually
   carries the `"/Available on"` marker (it reads like breadcrumb/cite text, not
   a heading) and add a precondition to `_ComponentSignals` -- the same 023
   item-3a treatment the other classifiers got. If a necessary class/id exists,
   the full-component `get_text` only runs on real candidates.
2. **Scope the text probe.** If the marker always lives in a specific element
   (e.g. a cite/breadcrumb span), probe that element's text instead of the whole
   component -- turning a full-subtree walk into a scoped one.
3. **Confirm the fallback still earns its place.** Check on the corpus whether the
   `span.mgAbYb == "Available on"` heading path alone catches every
   `available_on` component; if the `/Available on` text fallback never fires (or
   only fires on a structurally-identifiable shape), it can be gated or dropped.
   Pin with a targeted test before/after.

   **Measured (2026-06-01):** the corpus has **2 `available_on` components (of 87
   SERPs)**, and **both are caught by the cheap `span.mgAbYb` heading path** -- the
   full-component `/Available on` text fallback fires **0 times** corpus-wide,
   despite running ~4,320 times/pass. So the fallback is pure overhead on the
   fixtures and cannot be *proven* necessary by snapshots. It presumably guards
   real-world SERPs whose heading isn't `mgAbYb`, so deleting it outright is an
   unpinnable behavior change -- but **gating it behind a structural precondition**
   (direction 1) removes the per-component cost while preserving the real-world
   path, and the snapshot suite confirms the corpus classification is unchanged.

This is the highest-ROI single classifier change surfaced so far: a per-call
cost (full-component text) paid on nearly every component, addressable without
touching any parser. The measurement above points the implementation at
direction 1 (gate the fallback on a necessary signal) rather than removal; add a
targeted test that pins a non-`mgAbYb` `available_on` shape so the gated fallback
stays exercised.

## Verification gate (per change)

- `uv run pytest` -- 87 snapshots green **without updates**, full suite passing.
- Back-to-back A/B of `scripts/bench_parse.py` over the fixture corpus, same
  session, clearing the noise floor; record numbers in this plan's Log.
- `ruff check` / `ruff format --check` clean.

## Status (2026-06-06)

Picked up in the v0.10.0 cycle. **None of the three levers are implemented yet.**
The only commits that reference this plan (`ff4ea24`, `92e24e1`) edited *this
document* -- adding Lever 3 and recording its corpus evidence; no code changed.
Verified against current source:

- **Lever 1** -- `classifiers/main.py:_ComponentSignals.__init__` still does the
  unconditional `names.add(name)` / `ids.add(el_id)` per element (no interest-set
  restriction); matches the "before" state described above.
- **Lever 3** -- `available_on` still carries precondition `None`
  (`classifiers/main.py:112`) and the ungated full-component `get_text(node)`
  fallback (`classifiers/main.py:170`).
- **Lever 2** -- still uninvestigated (no dedicated extractor profiling pass on
  record).

**Tooling / baseline drift since the plan was written** (the baseline table above
is plan-035's profile on Python 3.13.12 via `scripts/bench_parse.py`):

- The benchmark moved into the package: `scripts/bench_parse.py` is gone. Run it
  as `python -m WebSearcher.bench` -- `--profile`, `--profile-sort cumulative`,
  `--top`, `--runs`, and `--iterations` all carry over. Read every
  `scripts/bench_parse.py` reference in this plan (incl. the Verification gate) as
  `python -m WebSearcher.bench`.
- The fixture corpus is now the consolidated `tests/fixtures/serps.json.bz2` --
  still 87 records, but reconsolidated, so the plan-035 self-times no longer map
  1:1.
- Python is now 3.14 (was 3.13.12).

**Therefore, re-baseline before touching code.** Capture a fresh
`python -m WebSearcher.bench --profile` (plus a `--profile-sort cumulative` split
for Lever 2) on 3.14 over the current corpus, record it in the Log below, and gate
every change against *that* baseline rather than the plan-035 table. Re-confirm the
Lever 3 corpus evidence (fallback fires 0x; both `available_on` components caught
by the `span.mgAbYb` heading path, measured 2026-06-01) on the current corpus
before gating.

## Log

### 2026-06-06 -- fresh baseline (Python 3.14.3, 87-SERP corpus)

`python -m WebSearcher.bench` (50 iterations x 5 runs, `--no-save`):

- Inter-run corpus total: **median 1516.1 ms**, MAD 27.0 ms, spread 70.6 ms.
- Per-SERP: median 15.353 ms, MAD 5.759 ms, p90 30.7 ms, max 42.9 ms.
- **Noise floor ~3.6% (2x MAD)** -- roughly 10x the plan-035-era 0.3-0.5% (this is
  a loaded WSL2 box). Any wall-clock win must clear ~4% to be provable here.

### 2026-06-06 -- Lever 1, option 1 (names/ids interest sets)

Implemented in `classifiers/main.py`: module-level `_NAME_SIGNALS` (7 tags) and
`_ID_SIGNALS` (4 ids) -- the only `s.names`/`s.ids` tokens the chain gates on --
and filtered the `__init__` walk to add only those (a leading truthiness guard
narrows `str | None` for the type checker and short-circuits no-id elements before
the membership test, so only interest-set tokens reach `set.add`). `classes` kept
in full. Added sync-coupling comments at
both the interest-set definition and the classifier chain, since a new
precondition token not registered here would silently never fire.

- **Byte-identical:** `uv run pytest` -- 87 snapshots passed **without updates**,
  full suite 437 passed.
- **Timing A/B** (same box/session, 50x5): 1516.1 -> **1502.3 ms** = **-0.9%**,
  inside the ~4% noise floor -- not a provable wall-clock win.
- **Profile A/B** (`--profile`, 10 iterations = 870 parses), `_ComponentSignals.__init__`:

  | | self | cumtime | total calls/pass |
  |---|---|---|---|
  | old | 2.161 s | 2.801 s | 14.35M |
  | Lever 1 | 1.957 s | 2.375 s | 11.90M |
  | delta | **-0.20 s (-9.4%)** | **-0.43 s (-15.2%)** | **-2.45M** |

  The -2.45M calls is the predicted ~2.47M `set.add` elimination, confirmed. The
  frame got measurably cheaper; the absolute saving (~0.2 s self on an ~18.5 s run,
  ~1.1%) tracks the timing A/B and stays under the box noise floor.

**Read:** option 1 nets out in the *right* direction (the plan's open question) --
real, profile-proven frame reduction -- but its wall-clock ceiling is low because
the `css('*')` walk + `classes.update` (untouched) dominate the frame. This is the
plan's defined decision point ("A/B option 1, then decide whether option 3's shared
walk is worth the coupling"). **Decision (user, 2026-06-06): keep Lever 1 and do
Lever 3 next** (not option 3's shared walk). Lever 2 not started.

### 2026-06-06 -- Lever 3 (gate available_on on mgAbYb)

Re-confirmed the corpus evidence on the reconsolidated 87-SERP corpus
(`.claude/lever3_confirm.py`): 1092 main components; 2 `available_on` components
(`watch the office`, `where to watch breaking bad`), both caught by the cheap
`span.mgAbYb == "Available on"` heading; the full-component `/Available on` text
fallback fires **0x**. Both available_on components sit in a generic `ULSxyf`
wrapper (shared with `banner`), so `mgAbYb` is the only specific signal.

Gated the chain entry to `(ClassifyMain.available_on, lambda s: "mgAbYb" in
s.classes)`, stopping the expensive full-component `get_text(cmpt)` fallback on the
~10 non-available_on components/SERP that reach the classifier. The
preserve-the-non-mgAbYb-path version (direction 1) is not achievable -- that path
has no corpus example to identify a necessary signal -- so the speculative fallback
is dropped as evidence-backed dead code (**accepted real-world behavior change**: a
non-mgAbYb component carrying `/Available on` text would no longer type as
available_on; unobserved on the corpus, so snapshots cannot pin it).

- **Byte-identical on corpus:** 87 snapshots + 437 tests green, no updates;
  pyrefly + ruff clean.
- **Profile A/B** (cumulative, 870 parses): `available_on` cumtime **0.717 s -> ~0**
  (drops out of the top 45); `get_text` cumtime 1.66 -> 1.15 s (-0.51 s); total
  calls 11.90M -> 10.45M (**-1.45M**).
- **Timing A/B** (50x5): baseline 1516.1 -> Lever 1 1502.3 -> **Lever 1+3 1463.3 ms**
  (this run's noise floor ~1.1%). Lever 3 contributes **-39.0 ms (-2.6%)**; both
  levers together **-52.8 ms (-3.5%)** vs the original baseline.

**Read:** Lever 3 is the largest win in the plan so far and clears the noise floor
(its -2.6% > this run's 1.1% floor; the profile evidence is decisive). Lever 2 (the
extractor profiling pass) remains the open investigation.

### 2026-06-06 -- Lever 2 (extractor hot-path review): investigated, no gateable win

Captured the cumulative phase profile on the committed Lever 1+3 code
(`--profile-sort cumulative`, 870 parses). The extractor phase
(`ExtractorMain.extract` 2.23 s cum + `_get_dom_positions` 0.65 s + `reorder`
0.32 s, ~17% of parse) is diffuse -- no single dominant frame like `available_on`.
Biggest leaves and their verdicts:

- `_get_dom_positions` (0.650 s self) -- one full-document `css('*')` -> position
  map. `reorder._range` looks up arbitrary descendants in it, so the whole map is
  needed without restructuring. Structural.
- `subtree_css` (0.616 s self, 8,040 calls) -- `node.css(sel)` + self-exclude
  filter behind `_find_all_with_class`/`_kp_markers`. The C walk dominates and the
  semantics (exclude self, bs4 `find_all`) pin the shape.
- `is_valid` (0.413 s self, 25,460 calls) -- the only byte-identical micro-opt is
  hoisting its per-call `bad` set literal to a module constant (~25k set builds),
  worth ~5 ms (< the 1-4% noise floor). The per-candidate
  `css_first('div[id="tadsb"]')` is defensive (catches an *empty*, un-removed
  bottom-ads wrapper) and not safely removable.
- `extract_from_standard` detect loop -- the `any(subtree_css(...))`
  materialization only runs when a `kp-wp-tab-*` container exists (all 4
  `_STANDARD_LAYOUTS` gate on those ids); on a normal SERP every `detect_css`
  `css_first` returns None and no list is built. Not a hot path.
- `reorder._range` (0.250 s self) re-walks each main-component subtree with
  `elem.css('*')` just to read the last descendant's position -- the same subtree
  `_ComponentSignals` already walks during classify.

**Verdict: no standalone byte-identical, low-coupling win.** The genuine remaining
extractor saving is the plan's **option 3** -- one shared document walk feeding the
position map, the `_range` ends, and (where scopes align) the component signal sets
-- which the plan itself flags as coupling currently-independent phases and risking
the byte-identical contract. Deferred as a separate, gate-hard change rather than
forcing a sub-noise commit here, consistent with the plan's noise-floor gate. The
`is_valid` `bad`-set hoist is available as a trivial cleanup on request. Lever 2
closed as investigated.

### 2026-06-06 -- trivial cleanup + option 3 (safe slice)

User: "trivial then option 3."

**Trivial:** hoisted `is_valid`'s per-call `bad` set literal to a module-level
`_BAD_LABELS` frozenset (`extractor_main.py`) -- no longer rebuilt ~25k times/pass.
Byte-identical (87 snapshots + 437 tests, no updates).

**Option 3 (safe slice):** `reorder` runs *before* classify, so the
`_ComponentSignals` walk can't feed it by reuse; the realizable, low-coupling slice
is `reorder._range`, which materialized the whole component subtree (`elem.css('*')`)
only to read its last element. Replaced with `_last_descendant` (`components.py`) --
a right-spine descent to the last element child on the same live tree, so the picked
node is identical by construction.

- **Byte-identical, directly verified:** `.claude/verify_last_descendant.py` compares
  the new pick against old `elem.css('*')[-1]` for **all 1092 main components** ->
  **0 mismatches**. 87 snapshots + 437 tests green, no updates; pyrefly + ruff clean.
- **Profile A/B** (cumulative, 870 parses): `reorder_by_dom_position` 0.322 -> 0.170 s
  cum (**-47%**); `_range` 0.258 -> 0.117 s cum (**-55%**); new `_last_descendant`
  0.096 s cum. ~0.15 s of subtree materialization removed.
- **Timing A/B** (50x5): inconclusive this run -- noisy box (median 1507.8 ms, spread
  551 ms, ~4.3% floor vs the Lever-1+3 run's 1.1%), so the cross-run median isn't
  comparable. The frame-level profile evidence is decisive and the change removes real
  work byte-identically (same profile-proven / wall-clock-in-noise shape as Lever 1).

**Fuller option 3 deferred.** The big remaining walk is the per-component
`_ComponentSignals` `cmpt.css('*')` (1.96 s). Eliminating it needs a single
structure-aware document walk that attributes each element to its containing main
component and builds the signal sets, replacing both `_get_dom_positions` and the
per-component signal walks. Major restructure: the document walk currently runs
*before* extraction (to snapshot ad positions pre-removal), component boundaries
aren't known at that point, and the per-component signal sets must be reproduced
exactly -- high byte-identical risk for the gain. Not attempted without an explicit
go-ahead; recorded as the open structural lever.

The deferred fuller option 3 was moved to its own plan,
[044](044-shared-document-walk-signals.md).

### 2026-06-06 -- close: review gate (PR #157)

Ran `/code-review` over the branch diff (3 finder angles). **Clean -- no actionable
findings.** Interest-set tokens are an exact bijection with the chain's `s.names`/
`s.ids` tests; `_last_descendant` was stress-checked to 20,000 randomized trees (0
mismatches) on top of the 1092-component corpus probe; the `_BAD_LABELS` hoist is
provably identical. The one flagged item -- the `available_on` gate dropping the
non-`mgAbYb` `/Available on` fallback -- is the documented, intentional dead-code
removal (conscious no-op), not a defect. Review posted to the PR; no fixes needed.

## Retrospective

- **The plan's "may or may not surface a win" framing held exactly.** Lever 3 was the
  real prize (-2.6%, the only change to clear the noise floor); Lever 1 and the option-3
  safe slice were profile-proven but sub-noise on wall-clock; Lever 2 surfaced no clean
  win at all. Profiling first, committing on profile evidence (not noisy wall-clock),
  was the right discipline.
- **Re-baselining before touching code paid off.** The plan-035 table was stale (Python
  3.13 -> 3.14, `scripts/bench_parse.py` -> `python -m WebSearcher.bench`, reconsolidated
  corpus) and the dev box's noise floor turned out ~1-4% (vs the assumed 0.3-0.5%), which
  reframed every "is this a win?" call toward the profile rather than the stopwatch.
- **Direct equivalence probes beat trusting snapshots** for the byte-identical contract.
  The 1092-component `_last_descendant` check (and the `available_on` 0x-fallback
  re-confirmation) caught nothing wrong but made "byte-identical by construction"
  provable rather than hopeful -- worth the few minutes each.
- **Two user decisions shaped scope:** keep Lever 1 despite sub-noise wall-clock (profile
  evidence + it seeds Lever 3's gate infra), and gate `available_on` on `mgAbYb` accepting
  the unpinnable real-world behavior change. Both were genuine forks the plan flagged;
  surfacing them rather than guessing was correct.
- **Option 3 was right to split.** The safe slice (`_range`) was low-risk and shipped; the
  fuller shared-walk restructure (the 1.96 s `_ComponentSignals` walk) carries real
  byte-identical risk from the document-walk-runs-before-extraction ordering -- a separate
  plan ([044](044-shared-document-walk-signals.md)), not a rushed addition here.
