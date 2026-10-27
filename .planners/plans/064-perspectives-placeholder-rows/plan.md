---
id: 64
slug: perspectives-placeholder-rows
status: implemented
branch: feature/perspectives-placeholder-rows
created: 2026-10-26T13:40:53-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/211
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
- **2026-10-26T17:52:28-07:00** — PR opened: https://github.com/gitronald/WebSearcher/pull/211
- **2026-10-26T17:52:28-07:00** — Implementation notes.
    - Step 1 signal check: `data-init-vis="false"` is not a safe signal. In the fixture corpus 260 loaded cards (text and link) carry it, and the placeholder class `be9mkb` appears on 15 loaded cards. Every listitem without text also has no link, in the fixtures (27 of 443) and in a 1,500-SERP sample of a 2026-10 crawl (988 placeholders against 460 loaded cards). The fallback filters on `has_text`, as the other selectors do.
    - The fallback is shared, so `recent_posts` placeholders go too (3 rows in the fixtures), the same empty `role=listitem` card.
    - Snapshots: 5 records lose 30 rows (27 `perspectives`, 3 `recent_posts`), every one with `title`, `url`, `text`, and `cite` all `None`; no row added, `sub_rank` contiguous, `serp_rank` sequential. Four records carry perspectives placeholders, not the two the plan counted: `0287f7dfbfc8` and `f3ce392b5af9` arrived in the 2026-10 follow-up fixtures after the plan was written.
    - `test_perspectives_have_url` is back to its pre-063 form; new unit test `test_perspectives_placeholder_cards_are_not_rows`.
    - Gate: ruff, ruff format, pyrefly clean; 867 passed, coverage 85.06%.
- **2026-10-26T17:52:33-07:00** — Implemented: 5 commits ahead of `dev`.
