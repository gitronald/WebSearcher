---
id: 63
slug: parse-2026-10-layout-regressions
status: done
branch: feature/parse-2026-10-layout-regressions
created: 2026-10-26T12:57:47-07:00
concluded: 2026-10-26T13:45:31-07:00
pr: https://github.com/gitronald/WebSearcher/pull/209
---

# Parse the 2026-10 top stories, text ad, and AI banner layouts

## Plan

### Problem

A 2026-10 crawl parsed with 0.12.1 parses completely, and its organic results
reconcile against the DOM. But Google reworked four components since 2026-07,
and the parsers no longer match them. Every top-stories component and nearly
every text ad returns "no subcomponents parsed" (both were around 2% in 2026-07
captures). The AI-overview "Thinking" banner is typed as an empty knowledge
panel on a large share of SERPs, and the unknown count rose about tenfold.

### Findings

1. **Top stories.** The block is `g-section-with-header.yG4QQe` under
   `div.A6K0A`, headed by `span[aria-level=2].mgAbYb` ("Top stories", or "News"
   on finance pages). Every story card is an `a.aJWbwf`, whether the list is
   vertical or clustered into `div.MmyPhf` groups (with an optional "Also in the
   news" cluster). The title is still `div.n0jPhd`, the source name is in
   `div.MgUUmf`, and the age ("8 hours ago") is in `div.OSrXXb`. A trailing
   `a.jRKCUd` is the "More news" link. None of the selectors in
   `parse_top_stories` match.
2. **Text ads.** Each ad is a `div[data-text-ad]` holding a `div.v5yQqb`. It
   reuses the standard layout's pieces: link `a.sVXRqc` (now also carrying
   `data-pcu`, the landing URLs), title `div[role=heading]`, display URL
   `span[role=text]`. The description is `div.p4wth` and the sitelinks are the
   anchors of `div.qmaLCb`. The `div.uEierd` wrapper that
   `AD_SUBTYPE_SELECTORS["standard"]` keys on is gone, so no layout matches.
   The same ads also render mid-page in a `div.yhQgZb` root, outside
   `#tads`/`#tadsb`, under a level-2 `span.L8u9l` heading "Sponsored result" or
   "Sponsored results"; those reach `unknown`.
3. **AI-overview banner typed as knowledge.** The "Thinking" / "An AI Overview
   is not available for this search" banner (`EYwa3d` controller, no
   `div.mZJni` body) now arrives wrapped in a `div[jscontroller=qTdDb]`.
   `knowledge_panel` matches that controller first, so the banner never reaches
   `ai_overview_banner` at the end of the chain and becomes an empty
   `knowledge/panel` row. In every case seen, all text inside the `qTdDb`
   wrappers lies inside the banner. Location-chooser text, when present, sits
   outside them.
4. **"Featured results" band with `role=group`.** Film and person pages carry a
   `div[role=group][aria-label="Featured results"]` (`EGUFKc` controller) with
   `VisualDigest*` sub-results: a trailer (`inline-video`), images, and a
   `VisualDigestDescription` blurb ("Source: IMDb ..."). `knowledge_panel`
   only recognizes the band with `role=complementary`, so these reach
   `unknown`. `parse_knowledge_panel` already
   parses VisualDigest bands.
5. **Long tail.** A sports "Bracket" module (`span.mgAbYb` level-2 heading),
   and booking widgets ("Reserve a tee time", "Book an appointment",
   `jscontroller=aD8OEe`), one to three SERPs each.

### Decisions

1. Reuse existing types. The banner goes to `ai_overview/unavailable`, which
   already exists for this message, not to a new `notice` sub-type. The
   Featured results band goes to `knowledge/featured_results`. The new text
   ads stay `ad`, with their own sub-type.
2. The ad `url` stays the anchor's `href`, as in the standard layout. Turning
   `/goto` tokens into target URLs is plan 062; `data-pcu` is noted there as a
   source of ad landing URLs.
3. The related-products module saved before its items load ("Find related
   products & services" with a "Thinking . . ." placeholder and empty skeleton
   items) has no content to recover. It stays one empty `searches_related` row.
4. Booking widgets stay `unknown`. They are rare, and the static HTML holds
   only a widget shell.

### Steps

1. Fixtures: add one or two SERPs per finding (1 to 4) from the crawl to
   `tests/fixtures/serps.json.bz2`, each with a `note`.
2. `parse_top_stories`: fall back to `a.aJWbwf` cards; `parse_top_story` reads
   the cite from `div.MgUUmf` and the age from `div.OSrXXb`.
3. Ads: a `text_ad` layout keyed on `div[data-text-ad]`; register "Sponsored
   result" as a level-2 header text for `ad`.
4. Classifier: an `ai_overview` rule ahead of `knowledge_panel` for a banner
   whose `qTdDb` wrappers hold nothing but the banner.
5. Classifier: add the `role=group` Featured results band to
   `knowledge_panel`; capture the `inline-video` trailer as a
   `featured_results` row; add "Bracket" to the knowledge submodule headings.
6. Snapshots: update and review every changed snapshot; run the full gate.
7. Release a patch version.

### Acceptance

On a 2026-10 crawl after a reparse: `top_stories` and `ad` error rates under
3%, about 4 rows per top-stories component, no `unknown` rows starting with
"Sponsored", no empty `knowledge/panel` rows carrying the banner text, and the
SERP and `general` row counts unchanged.

## Log

- **2026-10-26T12:58:34-07:00** — Activated.
  - Branch: `feature/parse-2026-10-layout-regressions`
  - Base: `dev` at `c010f88`
  - Worktree: `.worktrees/063-parse-2026-10-layout-regressions`
  - PR: pending
- **2026-10-26T13:11:56-07:00** — PR opened: https://github.com/gitronald/WebSearcher/pull/209
- **2026-10-26T13:12:58-07:00** — Parsers, classifier rules, fixtures, and tests landed (commits 500ebbf..10fb44c); full gate green (829 passed, 113 snapshots, 84.87% coverage, ruff/format/pyrefly clean).
  - Top stories: `a.aJWbwf` fallback in `parse_top_stories`; `get_cite` reads `div.MgUUmf`; `parse_top_story` records the age from the last span of `div.OSrXXb` via `mark_timestamp_row`. Both selectors also exist in older top-stories, perspectives, recent-posts, latest-from, and local-news cards, so 42 existing snapshots gained a correct cite ("CNN") or age ("7 hours ago"); reviewed row by row, no other field moved. All `serp_rank` shifts come from fixture `42bc62be2985`, whose 2026-10 top stories went from an error row to 7 cards.
  - Text ads: a `text` layout keyed on `div[data-text-ad]` reuses `_parse_ad_standard_sub` with `div.p4wth` as its description (the heading itself carries `Va3FIb`, which the standard text lookup would read as the description), and `parse_ad_menu` gains a `div.qmaLCb` sitelink format. Rows keep the standard layout's `standard`/`submenu` sub-types rather than a new one, so ad sub-types stay comparable across layouts (decision 1 revised). The layout yields when `div.uEierd` is present: all 15 older ad fixtures carry `data-text-ad` inside that wrapper.
  - Mid-page ad block: step 3's header-text registration ("Sponsored result" at level 2) was dropped. It stole fixture `e828d00dc1b3`, a 2026-02 "Find related products & services" module that embeds a "Sponsored results" unit, from `searches_related` and lost its suggestions row. Replaced by an end-of-chain `ClassifyMain.text_ad` rule (`div[data-text-ad]` -> `ad`).
  - Banner: `ClassifyMain.ai_overview_wrapped_banner`, ahead of `knowledge_panel`, claims a component when every `qTdDb` wrapper's text equals the text of its `EYwa3d` banner and no other knowledge-panel marker (`_KNOWLEDGE_CONTENT_CSS`) is present. The existing parser then sets `sub_type="unavailable"`.
  - Featured results: `div[role=group][aria-label="Featured results"]` joins the knowledge-panel selectors; `_parse_visual_digest` emits the `inline-video` trailer (attrid `/media_common/media_item/trailer/<title>`) as a `video` row with that title. "Bracket" joins `_KNOWLEDGE_SUBMODULE_HEADINGS`.
  - Fixtures: 7 records via the sidecar `add_fixtures.py` (715c39159a62, 67e221b91701, 0e2fb5edf0bb, 60bf643e2bf8, 2a3fd2155d93, c3675409cbf7, dc60ac7b1e9b); corpus integrity passes.
  - `test_perspectives_have_url` now checks only rows with a title or text: the new fixtures carry perspectives carousel placeholders (`data-init-vis="false"`, no text or link) that parse to empty rows. See Handoff question 1.
- **2026-10-26T13:20:48-07:00** — Whole-crawl check: a 2026-10 crawl reparsed with this branch at 6bd6696 (0.12.2a0) and compared with its 0.12.1 parse. Every acceptance criterion holds.
  - Same SERPs, `general` rows, and component set on both sides.
  - `top_stories`: error rate 100% -> under 0.1% (two empty shells); about 4 rows per component.
  - `ad`: error rate 97% -> 1.2%; the remainder are "Sponsored hotels" / "Sponsored tickets & tours" carousels, a separate layout that also errored in 2026-07 captures. No `unknown` rows start with "Sponsored". About 3% of ad rows still have no url: a text-ad variant without `a.sVXRqc`, not chased.
  - Banner: empty `knowledge` rows carrying the banner text are gone (two remain), and no SERP's only row is a knowledge panel.
  - `unknown` rows fell by about 95%; the rest are booking widgets, a periodic table, and a destinations module.
  - Component type transitions, all four reviewed: `knowledge` -> `ai_overview` (the banner, all empty before); `ai_overview` -> `knowledge` (Featured results bands with an `EYwa3d` controller, which the end-of-chain banner rule had typed as hollow `ai_overview/flat` rows, now `featured_results` rows with trailers and images); `unknown` -> `knowledge`; `unknown` -> `ad`. The only same-type row-count changes are `top_stories` and `ad` components gaining rows.
- **2026-10-26T13:20:59-07:00** — Implemented: 10 commits ahead of `dev`.
- **2026-10-26T13:46:08-07:00** — Close prep: crawl batch ids dropped from the 7 new fixtures (provenance stays in each note) and crawl figures removed from this plan (25c3b8d); `tests/test_parse_serp.py` CRLF line endings restored after a scripted edit had rewritten the whole file as LF (cfd5270; the diff is now the one test).
  - Review follow-up (medium `/code-review`, posted on PR #209): 3 findings, all fixed in e28bca3 with regression tests. `ai_overview_wrapped_banner` now probes the `EYwa3d` controller before its union walk (confirmed waste: about 5.6% of classify time on the fixture corpus; `test_wrapped_banner_rule_needs_the_controller`). The top-story age is the last direct child span of `div.OSrXXb`, skipping the `span.Uz7khf` "Video" label, stripped (`test_top_story_age_skips_video_label`). `parse_ad_text` skips only units nested in a `div.uEierd`, so a bare unit beside a wrapped ad is kept (`test_text_ad_beside_wrapped_ad_is_kept`). Five lower-confidence candidates were dropped as not reproducible (qmaLCb on older ads, p4wth fallback, nested EYwa3d, trailer nesting, duplicate uEierd probe).
  - Gate after fixes: ruff, ruff format, pyrefly clean; 832 passed; 113 snapshots unchanged.

## Handoff

**State.** Done: code, fixtures, tests, changelog, and review fixes are on
`feature/parse-2026-10-layout-regressions`, merged through PR #209. The
release is the next step on `dev`.

**Open questions.**

1. Perspectives carousel placeholders: answered 2026-10-26, moved to plan 064
   (drop the empty rows at parse time; consumers reparse earlier captures for
   comparability). `test_perspectives_have_url` stays scoped to rows with
   content until then.

**Not verified.** The 46-row text-ad variant without `a.sVXRqc` (no url) was
not examined. The booking widgets stay `unknown` by decision 4.

## Retrospective

- The plan's markup notes were right, but two of its proposed mechanisms were
  wrong once tried: a "Sponsored result" header text stole an older
  related-products module, and a new `text` sub-type would have split ad
  counts across layouts. Running the snapshot suite and a per-row snapshot
  diff before committing caught both.
- Reuse-first paid off three times: the banner already had a type
  (`ai_overview/unavailable`), the role=group band already had a parser
  (VisualDigest), and the new text ad is the standard ad without its wrapper.
- The banner's scale was invisible from SERP-level counts (only the
  banner-only SERPs stood out); counting rows by their details text exposed
  it. Component-level type transitions from a whole-crawl reparse are the
  check that shows a new rule claims only what it should.
- Selectors added for a new layout also fire on older ones (cite and age on
  perspectives and friends). Here that was a gain, but it widens the snapshot
  diff, so review it as part of the change, not as noise.
- Scripted edits must preserve a file's line endings; one CRLF file was
  rewritten wholesale before review caught it.
