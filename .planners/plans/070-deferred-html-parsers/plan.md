---
id: 70
slug: deferred-html-parsers
status: active
branch: dev
created: 2026-11-01T15:23:16-08:00
concluded:
pr:
---

# Fill deferred HTML per parser and flag unshown cards

## Plan

### Context

Google ships much of a results page as inline `jsl.dh(id, html)` calls that a browser runs to
fill empty placeholders. A capture that runs no JavaScript holds those fragments only as script
text, so a parser sees empty placeholders and misses their links: carousel cards, collapsed topic
panels, match clips, video key moments, and People also ask answers. Empty cards with a fragment
were 0 of 27 in fixtures from before 2026-07, 2 of 21 on 2026-07-01, and 29 of 70 on 2026-10-26.

### Decisions

- Fill per parser, never across a whole page. A whole-page fill was tried and corrupted People
  also ask, knowledge headings, and ads, because fragments also hold dialogs and menus. Only an
  empty target is filled, so a browser capture keeps what it already ran.
- A card with no fragment still drops. Plan 064 was right to drop those.
- A row not shown on load stays in the output with `details.visible` false, recorded only when
  false. Dropping such rows is a separate choice a consumer can make from the flag.
- Key moments are entries in the video row's `details`, not rows of their own, so a video's
  moments do not change its component's row count.
- Apply the `data-init-vis` rule to `videos` and image carousels.
- `ads.py` keeps hidden ad cards and flags them, where it now drops them.
- A repeat across components stays. A repeat inside one component (a carousel and a section of
  `perspectives`) also stays for now.
- Keep `details.title` as Google's card has it, "YouTube" included. Engagement counts ("10.2K+
  likes") are not captured unless a consumer asks.

### Steps

1. Done on `dev`: `_deferred_html.py`, post carousels in `top_stories.py`, and match-header clips
   in `knowledge.py`, with `details.visible`, `details.section_heading`, and
   `details.section_summary` (0.14.2a1 and 0.14.2a2).
2. `data-init-vis` in `videos` and `images`.
3. Hidden ad cards kept and flagged in `ads.py`, in both carousel layouts.
4. Key moments in `videos.py`, and in `general.py` where a video result holds them.
5. AI overview source lists that sit in fragments.
6. People also ask answers.
7. Stable release.

Each step bumps with `stanza release prerelease -y` once pushed.

### How to check a step

Parse one saved page and compare it with its rendered screenshot, then diff a set of saved pages
against the prior commit, by position within each type, before accepting snapshots. Report rows
gained, rows lost, and any feature field that changed.

### Risks

- Row counts rise for any consumer that counts rows, since shown and unshown cards both appear.
  The changelog says so at release.
- Flags are set only when the parser fills a target or reads a marker, so a browser capture does
  not flag match clips, and `top_stories` cards carry no `data-init-vis`.

### Out of scope

- Links held only in data records (`window['W_jd']` arrays, never an `<a href>`).
- Running JavaScript at parse time.

## Log

- **2026-11-01T15:23:28-08:00** — Activated.
  - Branch: `dev`
  - Base: `dev` at `955c09a`
  - Worktree: none (main checkout)
  - PR: pending

## Handoff

- State: step 1 is done on `dev`.
- Not verified: whether expanders work when a saved page is opened offline; which script reads the
  data records.
