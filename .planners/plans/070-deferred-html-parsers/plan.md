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

- Capture types keep what each one has. Data is never dropped or merged so that `requests` and browser
  captures parse the same; a field goes beside the other, and a field empty on one capture type gets a
  search of the page before the gap is accepted.
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
- A repeat across components stays, and so does a repeat inside one component that differs in
  anything, such as a post in two sections. A row matching another in its component in every field
  but rank is dropped: over 149 pages that was 8 image rows, where Google showed an image twice.
- Engagement counts ("10.2K+ likes") are not captured for now. They are not a priority, and a later
  parse of the saved HTML can add them.

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
- **2026-11-01T16:27:54-08:00** — The fragment regex matched 3,030 of the 10,468 jsl.dh calls on the 149 pages, and none on 31 fixture pages with an older call form. Nothing reported the miss. It is replaced by a reader of the call's arguments, covering window.jsl.dh with either quote style and this.id with either quote style. All 10,468 are now read.
  Effect against the prior build: 14 older pages changed, all on video rows, which gain their title, channel, and thumbnail. No rows gained or lost, and no other feature changed. So the empty cards on older pages really have no fragment, which the earlier count could not have shown. About 6 ms per page of added cost went away by removing a word boundary that blocked the literal prefix search, and the scan is cached per page: about 9.3 ms per page now, against 10.3 before.
  features.deferred_calls and features.deferred_read now report the share read. A test pins it at every call for the fixture corpus, and a downstream pipeline run on the 28 sampled pages carried the counts through, at 1,539 of 1,539.
  A key moment title no longer falls back to parsing its aria-label, which was English only. An expander-only moment has a null title. No page in the set has that form alone.
  Released as 0.14.2a5.
- **2026-11-01T17:01:01-08:00** — Video titles: a videos row's title is now the heading's first part, and its source line goes to cite, read by position since the classes are generated. Any heading that is not two parts with a title in the first is read whole, as before. The line replaces an existing cite it contains (a bare YouTube on 37 rows), since it holds the only duration on those rows, and a different cite is kept. Over the 149 pages: 135 rows split, each new title a prefix of the old one and the rest of the old title found in the new cite. No other field changed, and no rows gained or lost. Released as 0.14.2a6.
- **2026-11-01T17:16:55-08:00** — Source cards: details.sources on requests captures had no title, snippet, or publisher, because the parser read them only from a payload that these pages mostly lack. The card holds them in its own markup, so it is now the fallback. A video's card adds channel and duration, which no payload has. Over the 149 pages: all 30 sources on requests captures now have all three fields, and 7 browser sources gain a duration and 2 a channel, with no existing value changed and no rows gained or lost. Tray items still have only a domain. Their titles appear in script data for 35 of 80 sampled items, which is not read. Released as 0.14.2a7.
- **2026-11-01T17:33:41-08:00** — AI overview answer text: on requests captures, list items and whole sections of the answer sit in fragments with targets inside div.mZJni, and were cut off. The parser now fills div.mZJni before reading it. Answer characters on the changed rows: 4,276 to 10,070 on one sample set, 2,945 to 5,109 on another, and 2,633 to 4,502 on requests fixtures. Sections went from 16 to 22, citations from 36 to 73, sources from 30 to 53, and follow_up from 0 to 12. No answer shrank, browser captures did not change, and a read of the recovered text found no interface text. This corrects the Log above on tray and cards: requests captures had few cards partly because of this bug. Released as 0.14.2a9.
  Checked and ruled out: no page in the 149 has a template element, so the unfilled calls are targets created by other fragments. Overviews marked not_loaded have no body anywhere, including in fragments, so nothing is recoverable there.
  Identical rows: a row matching another in its component in every field but sub_rank is dropped and the rest renumbered (0.14.2a8). Over 149 pages that removed 8 image rows, with no distinct row lost.
  Survey of unread fragment text by component on non-browser pages: most is interface text (AI Mode prompts, feedback dialogs, share menus). The matching is rough and has false positives, including overview headings and video cards the parser already reads, and only a few examples of each type were read.
- **2026-11-01T18:03:30-08:00** — Seven more parsers fill their own subtree (0.14.2a10). Each was first run with the fill on in a scratch harness and its gains read. Over 149 pages: 10 pages changed, no rows lost, no other type moved. A full folder of about 100,000 2026-10 pages then parsed with every jsl.dh call read and no page lost; the largest page is 94 rows. Rows added by a fill carry no flag unless they have a marker, so visible may overstate what was on screen for those rows.

## Handoff

- State: steps 1 to 5 are done on `dev` at 0.14.2a10, pushed. Step 6 needs no work (see the Log).
  Step 7, the stable release, waits on the owner.
- Open questions:
  1. Run-together `videos` titles. Answered 2026-11-01 and done in 0.14.2a6: the title alone, with the
     source line in `cite`.
  2. Forum results carry an "N answers" sublink that no parser reads: 5 links on the sample pages.
     An earlier version of this question said 26, which was every unparsed static link (14 have no
     text and 7 are others, such as jump links). The links probably reach the row's own thread, and
     none was resolved to check. Recommended: leave them out of this release. Open.
  3. Keep `details.title` as Google's card has it, "YouTube" included? Answered 2026-11-01: yes.
  4. Which remaining components to fill before the stable release? Answered 2026-11-01: fill them first.
     `products`, `images`, `buying_guide`, `most_read_articles`, `locations`, `twitter_cards`, and
     `short_videos` are done in 0.14.2a10. Left out on evidence: `knowledge` and `ad` take in interface
     text, `election_results` gains only repeated links, and `election_dates` needs new parser work.
- Limits of the counts: a rename of `jsl.dh` itself shows as `deferred_calls` falling to zero, not as
  a falling share, and nothing alerts on it beyond the warning `deferred_read` below `deferred_calls`
  prints for a consumer that checks. Selectors on Google's class names remain as fragile as before.
- Not verified:
  - No page was checked against a rendered screenshot in steps 2 to 5; the checks were the page diff
    and link counts.
  - Whether expanders work when a saved page is opened offline, and which script reads the data
    records.
  - What a tray item looks like once rendered. Its target sits under `display:none` on every page
    checked, so it is flagged as not shown.
  - No page in the set carries `data-init-vis` on `videos` or `images`, so that rule has flagged
    nothing yet. The `images` flags seen come from inline `display:none`.
