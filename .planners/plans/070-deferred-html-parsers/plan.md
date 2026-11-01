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
- **2026-11-01T15:46:34-08:00** — Steps 2 to 6. Over a set of 149 pages (121 fixtures and 28 sampled from 2026-10 crawls), diffed against the prior commit by position within each type: no rows lost, feature fields unchanged, and 15 ad rows gained. Parsed /goto links on the 28 sampled pages rose from 418 to 622 of 708. Parse time rose from 7.7 to 10.6 ms per page on those pages.
  Step 2: mark_hidden_row reads data-init-vis on the node itself, and image rows go through it. No page in the set has the marker on videos or images, so that part flags nothing yet. Inline display:none flagged 30 image rows on browser captures.
  Step 3: the 15 kept ad cards have titles and links.
  Step 4: details.key_moments on videos and general video rows (seconds, title, url). A tile holds moments behind its expander, its evlb card, or both, with the same links. Filling the evlb card also gives these rows their channel and date. Core fields are read before the fill. No moment lacks a title or url.
  Step 5: details.source_tray on AI overview rows, apart from details.sources, and all flagged not visible. Browser captures have as many tray items as source cards (88 and 88 on the 10 rows with both). requests captures have far more in the tray: 29 against 3 in fixtures, and 80 against 27 in sampled pages. A tray and its cards overlap and use different links on a /goto page, so a merged list would count a source twice. root_html and raw_serp_html moved to _common to break an import cycle.
  Step 6 needs no work: of 155 fragments inside People also ask pairs, none holds a /goto link. 44 hold text: 32 are AI Mode prompts, and the other 12 are short (the 8 read are error messages). The answer already shipped expanded under a first question was parsed before this plan.

## Handoff

- State: steps 1 to 5 are done on `dev` at 0.14.2a4, pushed. Step 6 needs no work (see the Log).
  Step 7, the stable release, waits on the owner.
- Open questions:
  1. A `videos` row's `title` runs its source into the heading ("A video YouTube · A channel May 20,
     2025"), while `details.title` is clean. Recommended: fix the top-level `title` before the
     release, since a reparse would otherwise carry it. Open.
  2. Forum results carry an "N answers" sublink that no parser reads, the largest remaining group
     on the sample pages (26 links). Recommended: add it to the result's `details` before the
     release. Open.
- Not verified:
  - No page was checked against a rendered screenshot in steps 2 to 5; the checks were the page diff
    and link counts.
  - Whether expanders work when a saved page is opened offline, and which script reads the data
    records.
  - What a tray item looks like once rendered. Its target sits under `display:none` on every page
    checked, so it is flagged as not shown.
  - No page in the set carries `data-init-vis` on `videos` or `images`, so that rule has flagged
    nothing yet. The `images` flags seen come from inline `display:none`.
