---
status: draft
branch:
created: 2026-05-30T00:00:00-07:00
completed:
pr:
---

# Knowledge Parsers Rethink + `parse_alink` Reconciliation

## Status

Deferred / not started. Split out of
`027-component-parser-class-vs-function-standardization.md`, which deliberately
scoped this out. 027 (class→function) can land independently of this plan;
this plan does not block it.

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

## Suggested sequencing (to be fleshed out)

1. Map every knowledge / knowledge_rhs sub_type to its current selectors,
   output fields, and `details` shape (inventory before redesign).
2. Decide dispatch shape + whether the two types share a spine.
3. Settle link parsing and reconcile `parse_alink` as a byproduct of (2).
4. Align `details` with the typed-details plan.

(Intentionally left as a skeleton — fill in after 027 lands and we decide how
far the knowledge rethink should go.)
