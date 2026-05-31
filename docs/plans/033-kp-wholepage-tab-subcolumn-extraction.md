---
status: done
branch: feature/kp-wholepage-subcolumn
created: 2026-05-31T15:16:14-07:00
completed: 2026-05-31T16:42:41-07:00
pr:
---

# Parse kp-wholepage tabs as mini-SERP sub-columns

On whole-page knowledge-panel SERPs (`div.kp-wholepage`, the entity card with tabs
like `kp-wp-tab-overview`, `kp-wp-tab-TvActor`, `kp-wp-tab-AIRFARES`, …), Google
embeds a **full results column inside the active tab** — not just organic links, but
specialized widgets, a top-stories carousel, and Q&A/resource panels. WebSearcher
currently mishandles this in several partial, inconsistent ways, silently dropping
and mislabeling content. This plan replaces the partial handling with one model:
**extract the tab content as a sub-column and run it through the same
classify→parse pipeline the main column uses**, adding new component types for the
specialized blocks.

## Background: how we got here

Found while auditing a 102k-SERP crawl: 1,046 SERPs had a knowledge panel and **zero
organics**. Sampling proved the organics were present in the HTML but dropped. The
fix evolved through several wrong turns (all documented in
[finding-extraction-gaps.md](../guides/finding-extraction-gaps.md)):

1. A `standard-kp-wholepage` layout that recovers `div.g`/`tF2Cxc` organics from the
   panel and emits them as `general` (shipped as an interim measure). It works when a
   tab is *all organics* (e.g. "footloose cast").
2. But auditing "az primaries" against the rendered HTML showed the interim recovery
   is **unsound for rich tabs**: it labels every `div.g` `general`, so it
   - **mislabeled** an election-dates widget (`div.kb0PBd`) as a `general` result, and
   - **missed** everything that isn't a `div.g`: a "Presidential primary results"
     panel (`div.LWiyT`), a `top_stories` block (`div.JNkvid`), and an "Election
     resources" Q&A panel (`div.T6zPgb`).
3. "aapl stock price" added two more wrinkles: organics rendered as **bare `tF2Cxc`**
   (no `div.g` wrapper) inside `div.A6K0A` containers that the `standard-overview`
   recipe extracts but whose general parser **collapses to one result**; plus one
   `tF2Cxc` that is a **People-Also-Ask source** (inside `div.related-question-pair`),
   which must *not* become a `general`.

The lesson: a kp-wholepage tab is a **mini-SERP**, so cherry-picking organic blocks is
the wrong abstraction. It must be parsed as a column of heterogeneous components.

## Current (fragmented) handling to replace

- `extractors/extractor_main.py::_STANDARD_LAYOUTS` recipes (`standard-overview`,
  `standard-songs`, `standard-sports-standings`, `standard-airfares`) — each pulls
  specific tab-content tokens (`TzHB6b`, `A6K0A`); they surface *some* organics on
  *some* panels and miss/collapse the rest.
- `extractor_main.py::_kp_wholepage_organics` + the `standard-kp-wholepage` label —
  the interim `div.g`→`general` recovery (commits on `feature/v0.9.0`).
- `classifiers/main.py::ClassifyMain.general` `format-06` (`"tF2Cxc" in cls`) — an
  interim hack so a bare `tF2Cxc` classifies as `general`.

All three are superseded by the sub-column model below.

## The structure (grounded in fixtures)

- Panel root: `div.kp-wholepage`. The active tab content lives under
  `div[id^="kp-wp-tab-cont-"]` (e.g. `kp-wp-tab-cont-overview`).
- The **sub-column** is the container of component blocks inside that tab. In the
  "az primaries" overview tab it is `div.HaEtFf`; each component is a
  `div.TzHB6b` block (organic blocks additionally carry `K7khPe`). Finance tabs
  ("aapl") instead group bare-`tF2Cxc` organics under `div.A6K0A`.
- Component blocks observed in one election overview tab, in order: organic, organic,
  election-dates widget, election-results panel, several organics, top_stories,
  organic, election-resources panel.

> Container/wrapper classes (`HaEtFf`, `TzHB6b`, `K7khPe`, `A6K0A`) are Google's
> obfuscated names and will drift; detection should anchor on the stable
> `kp-wp-tab-cont-*` id and treat the wrapper classes as hints, with fixtures pinning
> current values.

## Approach

1. **Detect** the layout: `#rso` (or the panel container) holds a `div.kp-wholepage`
   with a `kp-wp-tab-cont-*` content node containing component blocks. Label it
   `standard-kp-wholepage` (keep the layout-name distinction established for the
   generic case; recipes that natively and fully handle their panel keep their label).
2. **Extract the sub-column**: enumerate the tab content's component blocks (the
   `div.TzHB6b`-style children of the content container), as a list of nodes — the
   same shape `_main_column` consumes.
3. **Classify + parse each block** through the existing `ClassifyMain` + parser
   dispatch, exactly like main-column components, so:
   - organics → `general` (the general parser already handles `div.g` *and*, once
     split correctly, bare `tF2Cxc`; fold the `format-06` need into the parser, see
     below),
   - the top-stories block → `top_stories`,
   - genuinely-new blocks → `unknown` (then promoted to new types, below).
4. **Emit** the panel itself as `knowledge` (+ `knowledge_rhs` as today) alongside the
   sub-column components, ordered after the panel.
5. **Dedup + exclude**: drop a sub-column block already emitted by a recipe (when a
   recipe ran), and skip `tF2Cxc` inside `div.related-question-pair` (PAA sources).
6. **Fix the collapse** in `component_parsers/general.py::find_subcomponents`: a node
   holding multiple `div.tF2Cxc` with no `div.g` wrapper should split into one result
   per `tF2Cxc` (PAA-excluded), instead of the single-`[node]` fallback. This is what
   makes finance tabs ("aapl") yield all their organics, and lets the classifier hack
   (`format-06`) be removed.

## New component types

Each needs: a `ComponentType` in `component_types.py`, a `ClassifyMain` signal in
`classifiers/main.py`, a parser in `component_parsers/`, registration, and a fixture
+ snapshot. Detection anchors (current obfuscated classes — pin via fixtures):

| type (proposed) | signal (current) | content |
|---|---|---|
| `election_dates` | `div.kb0PBd` / `cvP2Ce` / `jGGQ5e` | dropdown widget of election dates |
| `election_results` | `div.LWiyT` | "Presidential primary results · <state>" results panel |
| `election_resources` | `div.T6zPgb.YC72Wc` | official "Election resources · <state>" Q&A/links panel |

Finance (aapl) needs investigation: confirm whether its overview tab carries finance
widgets beyond bare-`tF2Cxc` organics that also need a type.

> Names are proposals — confirm against existing `component_types` conventions before
> implementing. If these election widgets recur outside kp-wholepage, classify them in
> the main column too, not only in the sub-column.

## Build sequence

1. Sub-column detection + extraction; route through classify/parse. Land organics +
   `top_stories` correctly; specialized blocks surface as `unknown` (no mislabeling).
2. `find_subcomponents` multi-`tF2Cxc` split (+ PAA exclusion); remove `format-06`.
3. Dedup against recipe output + relabel; verify the recipe-native panels
   ("central park", "mater", "cheap flights") are unchanged or improved.
4. Remove the interim `_kp_wholepage_organics`/`standard-kp-wholepage` `div.g`-only
   recovery once the sub-column model subsumes it, and **re-audit + regenerate the 5
   existing `standard-kp-wholepage` snapshots by type** (their interim baselines are
   suspect — see Fixtures).
5. Add the new component types one at a time, each with classifier + parser + fixture
   + snapshot; assert the previously-`unknown` blocks now type correctly.
6. Finance variant.

## Fixtures

Already captured this session: "alicia keys lyrics", "education pronunciation",
"footloose cast", "election popular vote", "books by roger ebert" (corpus), plus
`temp/serps/{az_primaries,us_election}.html` to add. "aapl stock price" and "cheap
flights" are already corpus fixtures. Add one fixture per new component type, chosen
for structural diversity per [fixture-corpus.md](fixture-corpus.md).

> **Existing `standard-kp-wholepage` snapshots are suspect — re-audit by type, do not
> trust them.** The 5 fixtures above were snapshotted under the *interim* `div.g →
> general` recovery, which the green suite froze as-is. At least "election popular
> vote" is an election panel like "az primaries", so its committed snapshot almost
> certainly carries the same defects (a mislabeled election-dates widget as `general`,
> plus missing results / `top_stories` / resources panels). Part of this plan is to
> walk each of these five against its rendered HTML (guide check 4) and regenerate the
> snapshots from the sub-column parse — a passing snapshot diff alone is not evidence
> of correctness here, since the baseline itself is wrong.

## Verification (per the guide)

- No duplicate or over-split rows: compare type counts vs the pre-change snapshot;
  assert distinct, non-overlapping organic URLs; confirm structured results keep their
  `sub_rank`s.
- **Type-correctness, not just dedup**: every recovered block must match what the
  rendered HTML shows at that position — the failure that motivated this plan was a
  block that deduped cleanly but was the *wrong type*.
- Full corpus suite green; recipe-native panels unchanged or improved.

## Risks / open questions

- **Blast radius**: routing tab content through `ClassifyMain` and changing
  `find_subcomponents` affects how general components are parsed broadly — gate the
  `tF2Cxc` split to the multi-child case and verify the full corpus.
- **Container detection drift**: anchor on `kp-wp-tab-cont-*`, not the obfuscated
  wrapper classes.
- **Recipe overlap**: decide per panel whether the sub-column model *replaces* the
  `_STANDARD_LAYOUTS` recipe or augments it; replacing risks losing recipe-specific
  knowledge-tab cards — diff "central park"/"mater" output before/after.
- **New-type scope**: the election widgets may be specific to election queries; decide
  whether they belong in shared classification or a kp-wholepage-only path.

## Log

### 2026-05-31 — implementation (branch `feature/kp-wholepage-subcolumn`)

Implemented the sub-column model and the new component types. Suite green: **335
passed, 4 skipped, 86 snapshots**; corpus integrity (`verify_drops.py`) passes.

**Grounding (real SERPs).** Mapped the structure against `temp/serps/{az_primaries,
us_election,aapl_stock,good_times_cast,carry_on_movies}.html` plus all 19
`kp-wholepage` corpus records. Key findings that shaped the design:

- The block container varies: az/us nest organics under a `HaEtFf` grouping wrapper;
  good_times/carry_on/aapl put blocks as direct children of `kp-wp-tab-<Tab>`. So
  "TzHB6b children" is the wrong anchor. The robust rule is: pick the active
  `kp-wp-tab-cont-*` tab (most block markers), descend through sole non-marker
  wrappers to the block container, then flatten any grouping wrapper inside it.
- **Collapse gate.** Every mini-SERP case has `#rso` collapsed to the single panel
  (`rso_children == 1`) with no `div.g` organics outside the panel; every
  *complementary* side panel (define judgement, taylor swift, …) has organics
  elsewhere or no `kp-wp-tab-cont-*`. Gate = `div.kp-wholepage` present, no organics
  outside it, and the active tab has blocks. This fires on all 12 mini-SERPs and none
  of the 7 side panels.

**Recipe vs sub-column (the open question).** Decided to *keep* the `standard-overview`
/`standard-airfares` recipes for panels they natively and fully handle (blocks are
direct token children) and route through the sub-column only when a recipe
*under-extracts* (`_kp_recipe_underextracts`: the sub-column finds more blocks than the
recipe's direct `keep_tokens` children — the `HaEtFf`-nesting case). Result: the 7
recipe-native corpus snapshots (mater, central park, oscar, doctor zhivago, pitbull,
cheap flights, aapl) are byte-identical (aapl improved via the `tF2Cxc` split), and the
`standard-overview`/`standard-airfares` labels survive (`test_features_expose_main_layout`).
This honors "recipes that natively and fully handle their panel keep their label."

**Changes.**
- `extractors/extractor_main.py`: removed `_kp_wholepage_organics`; added
  `_kp_active_tab`, `_kp_marker_ancestors`, `_kp_emit_blocks`, `_kp_subcolumn`,
  `_kp_organics_outside`, `_kp_recipe_underextracts`; rewrote `extract_from_standard`
  to try recipes first, fall through to the sub-column when a recipe under-extracts,
  else detect the collapsed panel and return `top_divs + sub_column`.
- `component_parsers/general.py`: `find_subcomponents` now splits a multi-`tF2Cxc`
  no-`div.g` block into one result per organic, excluding PAA sources
  (`div.related-question-pair`). Gated to the multi-`tF2Cxc` case.
- Added `election_dates`, `election_results`, `election_resources` component types
  (`component_types.py`), classified via `ClassifyMainHeader` header text
  ("Election dates", "Election resources", "Election results"/"Presidential primary
  results"); `election_results`' live tracker carries no `role="heading"`, so a
  structural `ClassifyMain.election` anchors it on the stable `eer-masthead`/`eer-rc-b`
  classes. Parser: `component_parsers/elections.py` (heading + outbound resource links).
- `classifiers/main.py`: also classify the knowledge-vertical onebox
  (`[id$="__onebox_content"]`, e.g. the pronunciation practice widget) as `knowledge`,
  fixing a no-title `general` row exposed by the sub-column on `education pronunciation`.
- Fixture: appended `az primaries` to `tests/fixtures/serps.json.bz2` (sole carrier of
  all three election types — a kp-wholepage election mini-SERP) and regenerated its
  snapshot. Re-audited and regenerated the 5 suspect `standard-kp-wholepage` snapshots
  (alicia keys, education, footloose, election popular vote, books) by type and the
  aapl snapshot.

**Verification (guide checks).** Distinct organic URLs with no self-dupes; the only
general/other URL overlaps are pre-existing (books → Wikipedia) or legitimately distinct
components (footloose images carousel vs. organic); the only error rows are the
pre-existing `knowledge_rhs` "no subcomponents parsed". az_primaries types every block
correctly (10 organics + election_dates/results/resources + top_stories + knowledge +
knowledge_rhs, in DOM order, zero `unknown`).

**Finance variant — resolved.** The `aapl` overview tab carries only `top_stories`, a
PAA block, a bare-`tF2Cxc` organics bundle (now split to 9), and `searches_related` —
all existing types. The finance entity summary lives in the knowledge panel /
`featured_results`. **No new finance component type is needed.**

**Deferred.** `us_election.html` was *not* added as a fixture: its "From Ballotpedia and
others &lt;date range&gt;" calendar variant of the dates widget carries no heading and no
`eer-`/stable anchor, so it still classifies as `unknown`. az_primaries already covers
all three new types; adding a structural signal for the headingless calendar needs a
confirmed, drift-resistant marker (the obfuscated classes shared by az/us are not
trustworthy) and is left for follow-up. "Presidential primary results" (`LWiyT`) is
registered as an `election_results` header variant but does not surface as a top-level
block in the current fixtures (it nests inside the panel).

## Retrospective

What worked: grounding every decision in real SERPs before writing code. The
investigation surfaced three things the plan's spec had wrong or unknown — (1) the
plan's named anchor classes (`kb0PBd`/`cvP2Ce`/`jGGQ5e`, `LWiyT`→results,
`T6zPgb`→resources) are unreliable (generic kp classes appearing 30-40× per page, or
mapped to the wrong widget); heading text + the semantic `eer-` prefix proved far more
stable; (2) the block container is not uniformly "TzHB6b children" — it ranges from a
deep `HaEtFf` wrapper to direct tab children, which forced the descend-then-flatten
design; (3) the `format-06` classifier hack the plan said to remove was never actually
committed. The `rso_children == 1` collapse signal cleanly separated mini-SERPs from
complementary side panels across the whole corpus.

The decision to keep the working recipes (rather than replace them wholesale) kept the
blast radius to exactly the records that were broken, kept the witnessed layout labels
alive, and made "recipe-native panels unchanged or improved" literally true. The
adversarial audit (guide check 3/4) caught two regressions a green snapshot would have
frozen: a feedback/onebox block mis-typed as `general`, and verifying the footloose URL
overlap was two distinct components rather than a double-extraction.

Merged into `feature/v0.9.0` via `--no-ff` on 2026-05-31 (local integration branch, no PR).
