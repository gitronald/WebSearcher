---
id: 43
slug: twitter-cards-modern-serps
status: inactive
branch:
created: 2026-06-06T01:46:36-07:00
concluded:
pr:
---

# Audit Twitter component parsers against 2024-2026 SERP evolution

The Twitter classifiers and parsers (`ClassifyMain.twitter`, `twitter_cards.py`, `twitter_result.py`) target 2024-era markup (`div.eejeod`, `g-scrolling-carousel`, `div.tw-res`) that no longer appears on modern SERPs — Google has retired the standalone Twitter/X carousel.

## Plan

Retired without modern-coverage work.

- Twitter components fire on only 2 of 87 corpus SERPs, both crawled 2024-03-13 (`movement`, `oscar the grouch`): 8 `twitter_cards` rows total, zero `twitter_result`.
- The `div.eejeod` marker is absent from every 2026 SERP sampled.

Decision: keep the parsers as legacy-only — they still recover Twitter content from 2024-era crawls (card title from the handle, plan 024 phase 4), so they are not deleted. No modern-SERP coverage will be added. If the dead classifiers later become a maintenance cost, remove `ClassifyMain.twitter`/`twitter_type` and the two parsers in a dedicated cleanup.

## Retrospective

This plan was added late — at v0.9.0 documentation finalization — and immediately resolved to "retire" rather than implement; the corpus made the call obvious, since the layout was gone by 2026 and no selector work brings it back. Lesson: a parser for a discontinued SERP feature should be marked legacy-only (or scheduled for removal) when the feature disappears, not rediscovered and planned much later.
