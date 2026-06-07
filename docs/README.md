# Documentation

## Plans

Implementation plans for project features and improvements. Each plan ([`plans/`](plans/)) has YAML frontmatter tracking status, branch, and timestamps; the table below is the source of truth for what is planned, in progress, and done. Sorted drafts-first, then by completion (most recent first).

| # | Plan | Status | Completed | PR |
|---|------|--------|-----------|----|
| 044 | [Shared structure-aware document walk for component signals](plans/044-shared-document-walk-signals.md) | draft | — | — |
| 041 | [Improve knowledge_rhs parser coverage for fact rows and expandable boxes](plans/041-knowledge-rhs-parser-coverage.md) | draft | — | — |
| 039 | [Investigate browser-automation alternatives to undetected_chromedriver](plans/039-browser-automation-alternatives.md) | draft | — | — |
| 031 | [Automate the Locations CSV Download](plans/031-automate-locations-download.md) | draft | — | — |
| 019 | [Enrich video details from hidden `evlb_*` "About this result" cards](plans/019-video-details-from-evlb-cards.md) | draft | — | — |
| 018 | [Add a `visible` flag to parsed results](plans/018-visible-flag-on-results.md) | draft | — | — |
| 034 | [Replace the local_results sub_type header-slug with a closed category set](plans/034-local-results-sub-type-categories.md) | done | 2026-06-06 | [#159](https://github.com/gitronald/WebSearcher/pull/159) |
| 040 | [Add structural CSS dispatch path for buying_guide and products to reduce header-text dependency](plans/040-header-text-vs-structural-classification.md) | done | 2026-06-06 | [#158](https://github.com/gitronald/WebSearcher/pull/158) |
| 036 | [`_ComponentSignals` consolidation + extractor hot-path review](plans/036-component-signals-and-extractor-hotpath.md) | done | 2026-06-06 | [#157](https://github.com/gitronald/WebSearcher/pull/157) |
| 038 | [Consolidate .claude/skills from 8 to 4 and absorb every skill-only script](plans/038-consolidate-skills-absorb-scripts.md) | done | 2026-06-05 | [#152](https://github.com/gitronald/WebSearcher/pull/152) |
| 037 | [Audit scripts/: absorb demos into the package, extract skills, retire one-offs](plans/037-scripts-audit-and-reorg.md) | done | 2026-06-05 | [#152](https://github.com/gitronald/WebSearcher/pull/152) |
| 035 | [`get_text` native-`text()` fast path (post-selectolax benchmark)](plans/035-get-text-native-fastpath.md) | done | 2026-06-01 | [#145](https://github.com/gitronald/WebSearcher/pull/145) |
| 032 | [Annotate and prune the bulk SERP fixture corpus](plans/032-fixture-corpus-notes-and-pruning.md) | done | 2026-05-31 | [#143](https://github.com/gitronald/WebSearcher/pull/143) |
| 033 | [Parse kp-wholepage tabs as mini-SERP sub-columns](plans/033-kp-wholepage-tab-subcolumn-extraction.md) | done | 2026-05-31 | — |
| 030 | [Main-Section Layout: Known Issues & Follow-ups](plans/030-main-layout-known-issues.md) | done | 2026-05-30 | [#142](https://github.com/gitronald/WebSearcher/pull/142) |
| 028 | [Knowledge Parsers Rethink + `parse_alink` Reconciliation](plans/028-knowledge-parsers-and-alink-reconciliation.md) | done | 2026-05-30 | [#141](https://github.com/gitronald/WebSearcher/pull/141) |
| 027 | [Component Parser Standardization: Class vs. Function](plans/027-component-parser-class-vs-function-standardization.md) | done | 2026-05-30 | [#139](https://github.com/gitronald/WebSearcher/pull/139) |
| 026 | [Explore replacing bs4/lxml with selectolax in the parse path](plans/026-selectolax-parser-backend-exploration.md) | done | 2026-05-29 | [#138](https://github.com/gitronald/WebSearcher/pull/138) |
| 025 | [Reclassify people-also-ask / image-filter blocks out of `general`](plans/025-reclassify-misclassified-general-blocks.md) | done | 2026-05-25 | [#129](https://github.com/gitronald/WebSearcher/pull/129) |
| 024 | [AI Overview legacy-SGE recovery and parser coverage fixes](plans/024-ai-overview-sge-and-parser-coverage-fixes.md) | done | 2026-05-25 | [#127](https://github.com/gitronald/WebSearcher/pull/127) |
| 023 | [Parse Pipeline Optimization (Profiling-First Revision)](plans/023-parse-pipeline-optimization-revised.md) | done | 2026-05-24 | [#125](https://github.com/gitronald/WebSearcher/pull/125) |
| 022 | [Enrich AI overview with payload-sourced citations and richer sources](plans/022-ai-overview-payload-citations.md) | done | 2026-05-24 | [#123](https://github.com/gitronald/WebSearcher/pull/123) |
| 021 | [Promote AI Overview to a top-level component with a structured, section-aware parser](plans/021-promote-ai-overview-component.md) | done | 2026-05-13 | [#115](https://github.com/gitronald/WebSearcher/pull/115) |
| 020 | [Directives reparse audit fixes](plans/020-directives-reparse-audit-fixes.md) | done | 2026-05-10 | [#113](https://github.com/gitronald/WebSearcher/pull/113) |
| 015 | [JS-Driven URL Collection](plans/015-js-driven-urls.md) | done | 2026-03-29 | — |
| 011 | [Structured Data Sources in Google SERP HTML](plans/011-structured-data-in-html.md) | done | 2026-03-29 | — |
| 016 | [Standardize Data Models](plans/016-standardize-data-models.md) | done | 2026-03-15 | [#100](https://github.com/gitronald/WebSearcher/pull/100) |
| 002 | [Class Consolidation Plan: Models and Details Field](plans/002-class-consolidation.md) | done | 2026-03-15 | [#100](https://github.com/gitronald/WebSearcher/pull/100) |
| 001 | [Component Parser Details Field Documentation](plans/001-component-parser-details-field.md) | done | 2026-03-15 | [#100](https://github.com/gitronald/WebSearcher/pull/100) |
| 014 | [Tidy up and bump to 0.6.9](plans/014-bump-0.6.9.md) | done | 2026-02-22 | [#97](https://github.com/gitronald/WebSearcher/pull/97) |
| 013 | [DOM Position Reorder](plans/013-dom-position-reorder.md) | done | 2026-02-20 | [#95](https://github.com/gitronald/WebSearcher/pull/95) |
| 010 | [Classify "Things to know" as knowledge/things_to_know](plans/010-things-to-know-classifier.md) | done | 2026-02-20 | [#95](https://github.com/gitronald/WebSearcher/pull/95) |
| 012 | [Parsing Diagnostics](plans/012-parsing-diagnostics.md) | done | 2026-02-06 | [#95](https://github.com/gitronald/WebSearcher/pull/95) |
| 008 | [Add compressed test fixtures for CI](plans/008-ci-test-data.md) | done | 2026-02-06 | [#94](https://github.com/gitronald/WebSearcher/pull/94) |
| 007 | [Implement `get_text_by_selectors` refactor across WebSearcher](plans/007-formalize-get-title-prompt.md) | done | 2026-02-06 | [#94](https://github.com/gitronald/WebSearcher/pull/94) |
| 006 | [Formalize multi-selector text extraction with `get_text_by_selectors`](plans/006-formalize-get-title.md) | done | 2026-02-06 | [#94](https://github.com/gitronald/WebSearcher/pull/94) |
| 004 | [Ads Parser Format vs Other Component Parsers](plans/004-ads-vs-other-parsers.md) | done | 2026-02-06 | [#94](https://github.com/gitronald/WebSearcher/pull/94) |
| 003 | [Ad Parser Structure](plans/003-ad-parser-structure.md) | done | 2026-02-06 | [#94](https://github.com/gitronald/WebSearcher/pull/94) |
| 000 | [Component Parsers Refactoring Plan](plans/000-component-parsers-update.md) | done | 2026-02-06 | [#93](https://github.com/gitronald/WebSearcher/pull/93) |
| 009 | [Refactor FeatureExtractor into own file with dataclass](plans/009-refactor-feature-extractor.md) | done | 2026-02-06 | — |
| 005 | [Parser Updates (v0.6.7a2) — Completed](plans/005-parser-updates-v0.6.7a2.md) | done | 2026-02-05 | [#93](https://github.com/gitronald/WebSearcher/pull/93) |
| 043 | [Audit Twitter component parsers against 2024-2026 SERP evolution](plans/043-twitter-cards-modern-serps.md) | inactive | — | — |
| 042 | [Investigate missing URLs in the results_for local results variant](plans/042-local-results-results-for-urls.md) | inactive | — | — |
| 017 | [Parse Pipeline Optimization](plans/017-parse-pipeline-optimization.md) | abandoned | 2026-05-24 | [#125](https://github.com/gitronald/WebSearcher/pull/125) |
| 029 | [Knowledge `details` Schema Alignment](plans/029-knowledge-details-schema-alignment.md) | retired | 2026-06-06 | — |
