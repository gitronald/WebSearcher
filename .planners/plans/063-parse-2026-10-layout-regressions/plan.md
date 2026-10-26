---
id: 63
slug: parse-2026-10-layout-regressions
status: draft
branch:
created: 2026-10-26T12:57:47-07:00
concluded:
pr:
---

# Parse the 2026-10 top stories, text ad, and AI banner layouts

## Plan

### Problem

A 2026-10 crawl batch of 102,707 SERPs, parsed with 0.12.1, parses completely,
and organic results reconcile against the DOM. But Google reworked four
components since the 2026-07 batch (parsed with 0.11.4), and the parsers no
longer match them:

| Metric | 2026-07 batch | 2026-10 batch |
|---|---|---|
| `top_stories` rows with "no subcomponents parsed" | 2.6% (166 of 6,498) | 100% (1,510 of 1,510) |
| `ad` rows with "no subcomponents parsed" | 2.4% (20 of 849) | 96.7% (1,057 of 1,093) |
| `knowledge/panel` rows that are the AI-overview "Thinking" banner | -- | about 31,000 |
| unknown rows | 11 | 128 |

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
   `unknown` (about 95 rows in the batch). `parse_knowledge_panel` already
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
4. Booking widgets stay `unknown`. Each is one SERP in 100k, and the static
   HTML holds only a widget shell.

### Steps

1. Fixtures: add one or two SERPs per finding (1 to 4) from the batch to
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

On the 2026-10 batch after a reparse: `top_stories` and `ad` error rates under
3%, about 4 rows per top-stories component, no `unknown` rows starting with
"Sponsored", no empty `knowledge/panel` rows carrying the banner text, and the
SERP and `general` row counts unchanged.
