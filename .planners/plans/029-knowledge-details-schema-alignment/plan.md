---
id: 29
slug: knowledge-details-schema-alignment
status: retired
branch: null
created: 2026-05-30T14:10:38-07:00
concluded: 2026-06-06T16:11:02-07:00
pr: null
---

# Knowledge `details` Schema Alignment

## Status

Draft / not started (fleshed out 2026-05-31). Split out of
`028-knowledge-parsers-and-alink-reconciliation.md` (merged in PR #141), which
resolved four of its five open questions and deferred this one. 028's
groundwork — unified `parse_alink` in `_common.py` and table-driven dispatch —
is in place, so there are no blockers.

## Why this is its own plan

Every knowledge result carries a `details` dict, but the shape is ad-hoc and
diverges between sibling parsers. Unlike the rest of 028 (which was strictly
behavior-preserving), aligning `details` **will move parser output**, so it is
isolated here to keep the snapshot churn reviewable on its own. Plans `001` and
`002` documented the inconsistency and gestured at a "typed-details" direction
but never defined a concrete *target*, so this plan's first deliverable is a
**decision**, not a mechanical refactor.

## ⚠️ Coverage caveat (drives the whole approach)

**The SERP fixtures are a partial witness, not a specification.** The parsers
deliberately handle real-world variants that no fixture contains, and parts of
the current design capture cases we have no sample for. Concretely:

- `featured_snippet`, `finance`, `calculator`, `election` have **zero** fixture
  coverage (confirmed during 028 — they only gained synthetic pins).
- `election` is hard-coded to the literal `"2020 US election results"` heading —
  obviously a captured real case absent from fixtures.
- `dictionary` has **three** independent text-extraction paths (modern
  `data-attrid`, legacy `div.vmod`, legacy `span[jsslot]`); fixtures exercise at
  most one.
- `knowledge_rhs` has branches for `subtitle`, an `Images` grid (`img_urls`),
  and a "Things to know" RHS topics list that may be only partially witnessed.

Consequences that are **non-negotiable** for this plan:

1. **Source code is the spec.** Build the inventory by reading the parsers, not
   by sampling fixture output. A key/branch that no fixture hits is *not* dead —
   it is an unwitnessed real-world shape.
2. **Preserve, don't prune.** Do not remove or collapse a branch/key because it
   "looks unused." Information we can't see in fixtures is still produced in
   production.
3. **Green snapshots ≠ behavior preserved.** Snapshots only bound the witnessed
   subset. Every code-only shape must get a synthetic pinning test *before* it
   is touched (the Phase-2 pattern in `tests/test_knowledge_dispatch.py`).

## Inventory (source-derived, refreshed against current code)

### `knowledge.py` → `type="knowledge"`, `details["type"]="panel"`

Base keys set on **every** row: `heading` (str|None), `img_url` (str|None),
`type="panel"`; plus `urls` (list of `{url, text}`, deduped, `sep="|"`) when any
anchors are present. Per sub_type additions:

| sub_type | extra `details` keys | fixture coverage |
|----------|----------------------|------------------|
| `featured_results` | — (sets `parsed.url`/`parsed.text`) | ✅ fixture |
| `featured_snippet` | `text` (+ embeds `parse_general_result` title/url/cite into `parsed`) | ❌ none |
| `unit_converter` | `text` | ✅ snapshot |
| `sports` | `text` | ✅ snapshot |
| `weather` | — (base only) | ✅ snapshot |
| `finance` | — (base only) | ❌ none |
| `dictionary` | `text` (3 source paths) | ⚠️ partial (1 path) |
| `translate` | `text` | ✅ snapshot |
| `calculator` | — (base only) | ❌ none |
| `election` | `text` | ❌ none |
| `things_to_know` | `heading` (overrides base) | ✅ snapshot |
| `<dynamic slug>` | `urls` (filtered for `/search?`), `items` | ⚠️ partial (a few slugs) |
| `panel` (fallback) | `text` | ✅ snapshot |

### `knowledge_rhs.py` → `type="knowledge"`, `sub_type="panel_rhs"`

- **main:** `details` = `{img_urls?, subtitle?, urls?, items?, type="panel"}`,
  **or `None`** when nothing was extracted.
- **sub-sections:** `details` = `{type="hyperlinks", items}`, **or `None`**.

### Divergences to resolve

1. **`img_url` (singular str) vs `img_urls` (plural list)** — same concept, two
   names/shapes across the two parsers.
2. **Always-emit vs `None`** — `knowledge.py` always emits a `details` dict;
   `knowledge_rhs` emits `None` when empty.
3. **`heading` placement** — in `details` for `knowledge.py`, absent (replaced by
   `subtitle`) for `knowledge_rhs`.
4. **`text` placement** — in `details` for several `knowledge.py` sub_types, but
   on `parsed["text"]` for `knowledge_rhs`; `dictionary` writes it to *both*.
5. **Two `details["type"]` tags in one family** — `"panel"` and `"hyperlinks"`.

## Target options (decision required before any code)

- **(A) Typed models** — a dataclass/model per `details["type"]` (extends the
  `002` model-consolidation direction). Strongest validation; largest change;
  introduces a model layer the parsers must populate.
- **(B) Canonical shapes + shared builder** *(recommended starting point)* —
  keep dicts, but define a documented canonical key set per `details["type"]`,
  build them through a small helper in `_common.py`, and converge the divergent
  names (e.g. `img_url`→`img_urls`). Medium effort; composes with a future
  repo-wide pass without committing to a model layer now.
- **(C) Minimal convergence** — only reconcile the divergent keys (items 1–2
  above) and document; no enforced contract. Smallest; leaves the family only
  partially consistent.

## Decision points (for sign-off)

1. Target option A / B / C.
2. `img_url` → `img_urls`: converge to a list? Keep singular as a 1-element list
   so no information is lost for the singular-image case?
3. Empty `details`: unify on always-emit or on `None`?
4. Does `text` belong in `details`, on `parsed["text"]`, or both (resolve the
   `dictionary` duplication)?
5. Keep `panel` + `hyperlinks` as distinct `details["type"]` values, or unify?

Each answer must be checked against the **preserve-don't-prune** rule: a
convergence that drops a key only witnessed in production is information loss.

## Sequencing (coverage-aware)

1. **Inventory from source** — complete the table above with value types and
   the multi-path branches fully enumerated (esp. `dictionary`'s three paths).
2. **Classify coverage** — mark each shape fixture-covered vs. code-only. The
   code-only set today: `featured_snippet`, `finance`, `calculator`, `election`,
   `dictionary` legacy paths, and the `knowledge_rhs` `subtitle`/`img_urls`/
   topics branches.
3. **Pin the code-only shapes first** — extend `tests/test_knowledge_dispatch.py`
   with synthetic markup asserting each code-only `details` shape, *before*
   migrating. This is the only regression net those branches have.
4. **Decide the target** (the 5 decision points) — bring options + a
   recommendation for sign-off.
5. **Migrate** — update parsers to the target, regenerate snapshots, add
   per-shape assertions. Land as a single reviewable diff with the snapshot diff
   reviewed line-by-line (regen can mask unintended changes in covered cases).

## Verification strategy

- **Snapshots** bound the witnessed subset only.
- **Synthetic pins** (step 3) bound the code-only subset.
- Together they bracket the change; neither alone is sufficient. Treat any
  snapshot move as intentional-and-explained or a bug — never auto-accept.

## Risks & non-goals

- **Non-goal:** a repo-wide `details["type"]` refactor. The enum is shared by
  ~20 parsers; this plan is scoped to the knowledge family. A broader pass is a
  separate plan that can build on whichever target (A/B/C) is chosen here.
- **Risk:** normalizing/removing a branch whose real-world shape isn't in any
  fixture → silent information loss in production. Mitigated by source-driven
  inventory (step 1), preserve-don't-prune, and synthetic pins (step 3).
- **Risk:** snapshot regeneration hiding an unintended change in a covered case
  → line-by-line review of the regenerated snapshots.

## Dependencies

Builds on merged 028 (PR #141): unified `parse_alink`, table-driven dispatch,
`panel_rhs` registered. No blockers; can start with the inventory (read-only)
whenever.

## Log

- **2026-06-06 — retired (superseded).** Never started. Two things overtook the
  plan as written:
  1. **Inventory went stale.** Since drafting (2026-05-30), the RHS family was
     restructured (plans 033, 041): rows renamed from `type="knowledge"` /
     `sub_type="panel_rhs"` to `type="side_bar"` with `sub_type="panel"` /
     `"links"`, and new `details["type"]` values (`songs`/`albums`/`events`)
     were added from the kp-wholepage music sections. The tables above no longer
     match the code.
  2. **Decision point #1 was settled in practice.** The "details schema
     discipline" since adopted — *reuse the existing `details["type"]` labels
     (text/hyperlinks/ratings/place/panel/video); drop hollow payloads instead
     of emitting null-filled dicts* — is effectively **option (B)/(C)**, not
     (A) typed models. There is no longer a model-layer target to decide.
  The five divergences this plan catalogued are still real and unresolved
  (`img_url` vs `img_urls`, always-emit vs `None`, `heading`/`subtitle`
  placement, `text` in `details` vs `parsed["text"]`, multiple `details["type"]`
  tags). Its durable value — the preserve-don't-prune rule, the
  source-is-the-spec / synthetic-pin verification strategy, and the divergence
  catalogue — is carried forward into **plan 041**
  (`041-knowledge-rhs-parser-coverage.md`), which is actively reworking the
  `knowledge_rhs` `details` shapes under the same discipline. Retired (not
  abandoned): the goal is being met by another mechanism, not dropped.
