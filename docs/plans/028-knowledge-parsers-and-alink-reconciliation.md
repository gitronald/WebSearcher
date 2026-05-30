---
status: in-progress
branch: claude/post-merge-status-check-52Z1B
created: 2026-05-30T00:00:00-07:00
completed:
pr:
---

# Knowledge Parsers Rethink + `parse_alink` Reconciliation

## Status

In progress. Split out of
`027-component-parser-class-vs-function-standardization.md`, which deliberately
scoped this out. 027 (class→function) landed independently (PR #139).

## Decisions (locked)

- **Scope: full rethink.** Reconcile `parse_alink`, restructure the knowledge
  dispatch to be table-driven, share a spine between `knowledge` and
  `knowledge_rhs` where it pays off, align `details`, and close the sub_type
  registry.
- **`parse_alink` href-missing: lenient.** A missing `href` yields `url=None`
  rather than raising. In practice every current call site already guards
  `"href" in a.attributes` / `href is not None`, so this is forward-looking
  insurance, not a snapshot change (verified: all four call sites guarded).

## Why this is its own plan

The 027 audit found `parse_alink` duplicated across four parsers, but they are
**not hard duplicates** — and two of the four live in the knowledge parsers,
which we want to rethink more broadly rather than patch a shared helper onto.
Reconciling the helper and reshaping the knowledge parsers are the same body of
work, so they live together here.

## Finding 1 — `parse_alink` is three behaviors, not one

`parse_alink` is defined in `general.py`, `knowledge.py`, `knowledge_rhs.py`,
and `top_image_carousel.py`. With `get_text`'s default separator being `""`:

| File | url access | text separator | `None`→`""` |
|------|-----------|----------------|-------------|
| `general.py` | `a.attributes["href"]` (strict) | `""` | yes |
| `knowledge_rhs.py` | `["href"]` (strict) | `""` | yes |
| `knowledge.py` | `["href"]` (strict) | `"\|"` | yes |
| `top_image_carousel.py` | `.get("href") or .get("data-url","")` | `"\|"` | no |

Only `general.py` and `knowledge_rhs.py` are byte-identical. The other two
differ intentionally: `knowledge.py` joins multi-fragment link text with
`"\|"`; `top_image_carousel.py` needs the `data-url` fallback (lazy-loaded
carousel images) and leaves text un-coalesced.

**Caution:** the strict `["href"]` variants raise `KeyError` on a missing href,
which `run_parser` converts into a whole-component parse error. Collapsing to
`.get("href")` would silently produce `url=None` instead — a behavior change,
not a pure refactor.

Reconciliation options, smallest to largest:
- **(i)** Dedup only the two identical defs (`general` ↔ `knowledge_rhs`).
  Safe, low value.
- **(ii)** One parameterized helper
  `parse_alink(a, sep="", data_url_fallback=False)` called with explicit args
  per site. Requires deciding the href-missing semantics (keep strict, or go
  lenient `.get` and accept the change) and the carousel coalescing rule.

## Finding 2 — the knowledge parsers are due for a rethink

`knowledge.py` (218 lines) is a single `parse_knowledge_panel` with a large
`if/elif` sub_type cascade — at least 13 branches:

`featured_results`, `featured_snippet`, `unit_converter`, `sports`, `weather`,
`finance`, `dictionary`, `translate`, `calculator`, `election`,
`things_to_know`, a **dynamic** `slugify(heading)` branch, and `panel`.

`knowledge_rhs.py` (157 lines) handles right-hand-side panels as a separate
type (`parse_knowledge_rhs` + main/sub helpers) and shares no code with
`knowledge.py` beyond its own copy of `parse_alink`.

### Open questions to drive the rethink

- **Dispatch shape:** is the 13-branch cascade in `parse_knowledge_panel` the
  right structure, or should sub_type detection/parsing be table-driven
  (classifier → handler map), the way `notices.py` / `ads.py` route sub-types?
- **`knowledge` vs `knowledge_rhs`:** two types, two files, overlapping intent.
  Should they share extraction/link/details helpers, or stay fully separate?
- **`details` schema consistency:** what shapes does each knowledge sub_type
  emit, and do they conform to the typed-details direction from
  `002-class-consolidation.md` / `001-component-parser-details-field.md`?
- **The dynamic `slugify` sub_type branch:** is an open-ended sub_type space
  desirable, or should sub_types be a closed registry set (cf. the
  `sub_types=(...)` field on `ComponentType`)?
- **Link parsing:** once the above is settled, where does the shared link
  helper live (`_slx.py`, a `component_parsers/_common.py`, or per-parser),
  and which `parse_alink` behavior wins per call site?

## Inventory (step 1 — done)

Source-of-truth survey driving the redesign:

- **`parse_alink`**: 4 defs, 3 behaviors (table in Finding 1). All call sites
  guard href presence today.
- **Dispatch**: `parse_knowledge_panel` is a 13-branch `if/elif` cascade.
  Branch order is significant and two branches are *conditional consumers*:
  - `things_to_know` matches on `span[role=heading].IFnjPb` presence but only
    sets `sub_type` when the heading text is in the known set — otherwise the
    chain is consumed with **no `sub_type` key** (must be preserved).
  - the dynamic `slugify` branch requires *both* `div.JNkvid` **and** a
    `[role=heading][aria-level=2]`; with JNkvid but no section heading it falls
    through to `panel`.
- **Registry drift**: `extractor_rhs.py` assigns component `type="knowledge_rhs"`
  (registry-valid), but `parse_knowledge_rhs` normalizes result rows to
  `type="knowledge"`, `sub_type="panel_rhs"`. `"panel_rhs"` is **absent** from
  the `knowledge` ComponentType's `sub_types` tuple. The dynamic `slugify`
  branch also mints sub_types outside any closed set.
- **Snapshot coverage** (the safety net): `panel`, `panel_rhs`,
  `featured_results`, `translate`, `weather`, `unit_converter`,
  `things_to_know`, `sports`, `dictionary`. **Uncovered**: `featured_snippet`,
  `finance`, `calculator`, `election`, dynamic `slugify`. These need pinning
  unit tests authored *before* the dispatch refactor.

## Sequencing (resolved)

**Phase 1 — `parse_alink` reconciliation.** New `component_parsers/_common.py`
with one parameterized `parse_alink(a, sep="", data_url_fallback=False)` (lenient
`.get`) + the shared `parse_alink_list`. Repoint all four parsers; delete the
four private copies. Output-preserving (all call sites guarded; no carousel
snapshots exist).

**Phase 2 — table-driven knowledge dispatch.** Convert the 13-branch cascade to
an ordered `(detector, handler)` registry mirroring `notices.py`/`classifiers`.
Mechanical / behavior-preserving by construction. Author pinning unit tests for
the five uncovered sub_types first.

**Phase 3 — shared spine + `details` + registry close-out.** Factor the
extraction helpers shared by `knowledge` and `knowledge_rhs` (link list, image
grid, details assembly) into `_common.py`. Add `panel_rhs` to the registry;
decide the dynamic `slugify` sub_type's fate (closed registry vs documented
open set). Align `details` shapes with the typed-details direction
(`001`/`002`).

Each phase is a separate commit, gated on the full suite staying green
(snapshots updated only where the lenient/coalescing change is intentional).
