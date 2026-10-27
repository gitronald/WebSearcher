---
id: 64
slug: perspectives-placeholder-rows
status: active
branch: feature/perspectives-placeholder-rows
created: 2026-10-26T13:40:53-07:00
concluded:
pr:
---

# Drop empty perspectives placeholder rows

## Plan

### Problem

Perspectives carousels ("What people are saying") pre-render a placeholder for
every card not yet loaded at capture: a `div[role=listitem]` with
`data-init-vis="false"` and the class `be9mkb`, about 300 bytes, holding no
text and no link. `parse_top_stories` falls back to `[role="listitem"]` for
perspectives and keeps every match, so each placeholder becomes a
`perspectives` row with `title`, `url`, `text`, and `cite` all `None`.

In the fixture corpus, 10 of 420 `perspectives` rows are placeholders, all on
the two 2026-10 top-stories records added in plan 063 (`715c39159a62`,
`67e221b91701`). In crawl-scale captures, from 2026-07 on, they are a large
share of all `perspectives` rows. Plan 063 left them in place and scoped
`test_perspectives_have_url` to rows with a title or text (its Handoff
question 1).

### Decisions

1. Drop the placeholders at parse time, not downstream: a row with no
   content and no link is not a result.
2. Comparability is handled by reparsing, not by keeping the rows. A consumer
   comparing captures across time reparses its earlier captures with the
   release that carries this change; the changelog entry says so.

### Steps

1. In the `role=listitem` fallback of `parse_top_stories`, keep only items
   with text (`has_text`), as the other selectors in that function already
   do. Check first whether `data-init-vis="false"` alone is the safer signal:
   a loaded card that carries no text but has a link would be dropped by
   `has_text`.
2. Restore `test_perspectives_have_url` to assert on every `perspectives` row.
3. Add a unit test: a carousel with one loaded card and two placeholders
   parses to one row.
4. Update and review the snapshots (the two plan-063 records lose their
   placeholder rows; `sub_rank` stays contiguous); run the full gate.
5. CHANGELOG entry under `[Unreleased]`, flagged as a row-count change for
   `perspectives`.

### Acceptance

No `perspectives` row in the fixture corpus has `title`, `url`, `text`, and
`cite` all `None`; loaded cards keep their rows and order.

## Log

- **2026-10-26T17:47:42-07:00** — Activated.
  - Branch: `feature/perspectives-placeholder-rows`
  - Base: `dev` at `ebe1b64`
  - Worktree: `.worktrees/064-perspectives-placeholder-rows`
  - PR: pending
