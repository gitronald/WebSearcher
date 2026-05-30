---
status: draft
branch:
created: 2026-05-30T00:00:00-07:00
completed:
pr:
---

# Knowledge `details` Schema Alignment

## Status

Draft / not started. Split out of
`028-knowledge-parsers-and-alink-reconciliation.md`, which resolved four of its
five open questions (dispatch shape, knowledge-vs-rhs sharing, the dynamic slug
policy, and link-helper location) but deliberately deferred this one.

## Why this is its own plan

The knowledge parsers each emit an ad-hoc `details` shape:

- `knowledge.py` — `{heading, urls, text, img_url, items?, type="panel"}`
- `knowledge_rhs.py` main — `{img_urls?, subtitle?, urls?, items?, type="panel"}`
- `knowledge_rhs.py` subs — `{type="hyperlinks", items}`

Plans `001-component-parser-details-field.md` and `002-class-consolidation.md`
documented the *problem* (inconsistent, untyped `details` across all parsers)
but never defined a concrete typed-details *target*. Aligning the knowledge
parsers therefore is not a mechanical refactor — it requires first deciding the
target schema, then rewriting parsers and regenerating snapshots together. That
output churn is broad and is best reviewed on its own, separate from the
behavior-preserving dispatch/reconciliation work in 028.

## Sequencing (to flesh out)

1. **Inventory.** Enumerate every `details` shape each knowledge / knowledge_rhs
   sub_type emits today (key set, value types, `type` tag). The table in `001`
   is a starting point but predates several plan-024+ parser changes.
2. **Decide the target.** A typed-details model (cf. `002`) vs. a documented set
   of canonical `details["type"]` shapes. Decide whether `urls` / `items` /
   `text` keys converge across sub_types.
3. **Migrate.** Update parsers to the target, regenerate snapshots, and add
   per-shape assertions. Land as a single reviewable diff (snapshot churn
   isolated from 028).

## Dependencies

Builds directly on 028 (table-driven dispatch + unified `parse_alink`). No
blockers; can start whenever the typed-details target is decided.
