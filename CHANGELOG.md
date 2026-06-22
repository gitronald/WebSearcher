# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

- **Breaking:** removed the `selenium` (undetected-chromedriver), `zendriver`, and `playwright` browser backends, leaving `patchright` (now the **default**) and `requests` (the no-browser HTTP path). Constructing `SearchEngine(method="selenium"|"zendriver"|"playwright")` now raises (the `SearchMethod` enum no longer defines them), the default backend changes from `selenium` to `patchright` (a bare `ws.SearchEngine()` launches patchright instead of undetected-chromedriver), and `SeleniumConfig`/`ZendriverConfig` and the `selenium_config`/`zendriver_config`/`playwright_config` kwargs are gone. **Migration:** pass `method="patchright"` (now the default) and run `patchright install chromium` once -- the browser binary is a new required post-install step pip can't run automatically. The install footprint drops `selenium` + `undetected-chromedriver` and adds `patchright` (which bundles its node driver); `requests` is unchanged. This is plan 039's green-lit migration follow-up, now that plan 049 confirmed patchright runs headed on a no-display host via Xvfb (plan 051)
- Dropped the `ws-demo` `--headless` flag -- the browser backend must run *headed* (Chrome's own `--headless` is reliably blocked by search engines), so the flag only exposed a non-working path for live collection; the `PatchrightConfig(headless=...)` passthrough is unchanged

## [0.10.2] - 2026-06-21

- Documented running the browser backends without a GUI -- on a headless server, CI runner, or container -- via an [Xvfb](https://www.x.org/releases/X11R7.7/doc/man/Xvfb.1.xhtml) virtual display (new README section). The browser backends must run *headed* (Chrome's own `--headless` is reliably blocked), so a no-display host needs a virtual display; confirmed end to end with the `patchright` backend (plan 049)

## [0.10.1] - 2026-06-21

- **Breaking (internal):** reorganized the flat parse modules into a single `WebSearcher.parsers` package -- `parsers.py` -> `parsers/parse_serp.py`, `component_parsers/` -> `parsers/components/`, and the top-level `component_types`/`components` modules folded in. Public entrypoints are unchanged (`import WebSearcher; WebSearcher.parse_serp`, and `from WebSearcher.parsers.parse_serp import parse_serp`), but deep imports of the old flat paths must switch (`from WebSearcher.parsers import parse_serp` -> `from WebSearcher.parsers.parse_serp import parse_serp`; `WebSearcher.component_parsers.<x>` -> `WebSearcher.parsers.components.<x>`)
- Hardened the parse pipeline (output byte-identical, pinned by the snapshot suite): every component is now classified before any is parsed, so the two DOM-mutating parsers (`general`, `ai_overview`) can no longer make a later component's classification depend on parse order; `Component.to_dict()` returns a shallow copy so callers can't mutate the live attribute table; and the local next-sibling walk is replaced by the shared `_slx.next_sibling` helper
- Dev tooling: dropped the `snakeviz` and `ipykernel` dev dependencies, fully evicting transitive `tornado` (which carried four open advisories) -- benchmark profiling now uses the stdlib `pstats`. Also added `.github/copilot-instructions.md`, made the README framing generic with the demo version aligned, and pointed the locations demo's geotargets download at the demo data dir

## [0.10.0] - 2026-06-20

- Reliable block/CAPTCHA detection: Google's `/sorry/` block redirect is now detected from the response URL (`utils.is_sorry_redirect`), not just the literal "CAPTCHA" in the page text. `parse_serp` accepts an optional `url` that feeds `features["captcha"]`, and `SearchEngine.parse_serp` passes it automatically. The browser backends (`selenium`, `patchright`, `playwright`, `zendriver`) now capture the live URL and rendered HTML when the `#search` wait times out (only when navigation actually moved off the prior page, recording the real HTTP status e.g. 429), and the `requests` backend records the final post-redirect URL -- so a challenge page is saved instead of discarded. `SearchEngine.parse_serp` also resets the previous parse each run so a swallowed error can't leave a stale `captcha` flag on the wrong query, and the `ws-demo searches` CAPTCHA guard now fires on a redirect block
- Added `update_locations_file` (alongside `download_locations`): downloads the latest Google geotargets CSV to one stable path and appends a row to an append-only ledger, change-detecting on the upstream filename's embedded release date so an unchanged upstream is a no-op. Runnable as `python -m WebSearcher.locations`; the repo now tracks both files (history seeded from a 26-snapshot archive spanning 2018-2026) and a weekly GitHub Actions cron refreshes them via a `data`-labeled PR
- Richer parsed output under the two-tier result schema: right-hand knowledge-panel entity facts now parse to `side_bar` rows with `sub_type="fact"` (label in `title`, value in `text`, source/links in `details`) instead of being dropped or flattened; video `details` are enriched from the hidden `evlb_*` "About this result" cards for `general[sub_type=video]`, `videos`, `top_stories`/`perspectives`, and `short_videos`; a `details["visible"] = false` flag marks items under inline `display:none` lazy-render containers; and item `timestamp` (relative date) is recorded in `details` for `news_quotes`, `twitter_result`, `view_more_news`, and `videos`. The `knowledge` panel `details` converged with the schema (keys only when informative, singular `img_url` -> a 1-element `img_urls` list), and a non-empty `details` always carries a `type`
- **Breaking (output):** moved the per-result `error` field into the `details` extras bucket -- a parse failure now surfaces as `details = {"type": "item", "error": "<message>"}`; read `r["details"]["error"]` (guarding `details is None`) instead of `r["error"]`
- **Breaking (output):** replaced the `local_results` `sub_type` header-slug derivation with a closed set (`places`, `locations`, `businesses`, `availability`); a header outside the set now carries no `sub_type` (the raw header is preserved in `details["heading"]`), so consumers filtering on the old slug values must switch
- **Shape note (output):** video `details` keys are now emitted only when populated (previously None-padded from selectors stale on modern SERPs) -- use `details.get(...)` rather than bracket access
- Made `buying_guide` and `products` classification robust to non-English or reworded headings via a structural CSS-class dispatch path ahead of the header-text match, and gated the `available_on` classifier on its `mgAbYb` heading (observed classifications unchanged). Optimized the parse hot path ~3.5% (byte-identical, snapshot-pinned)
- Added `SearchEngine.to_record()` / `save_record()` -- one merged per-SERP JSON record (collection metadata sans HTML, plus `features` and `results`), folding the separate `save_search` + `save_parsed` writes into a single line; `save_record(ws_version=...)` stamps a distinct `ws_version` so a later reparse never clobbers the collection-time `version`
- Dev tooling: replaced Dependabot with self-hosted [Renovate](https://docs.renovatebot.com) for dependency-update PRs (release cooldown, per-ecosystem grouping, SHA-pinned actions, no auto-merge); Dependabot vulnerability alerts stay enabled
- **Breaking (internal):** renamed the `WebSearcher.search_methods` subpackage to `WebSearcher.searchers` (the `SearchEngine` module moved into it). Public entrypoints are unchanged, but direct backend imports must switch from `WebSearcher.search_methods.<backend>_searcher` to `WebSearcher.searchers.<backend>_searcher`

## [0.9.0] - 2026-06-06

- **Breaking (internal):** rewrote the parse pipeline natively on [selectolax](https://github.com/rushter/selectolax) (lexbor backend) for ~2x faster parsing, dropping the BeautifulSoup + lxml runtime dependencies. The `parse_serp` / `SearchEngine` API and core output schema are unchanged, but `make_soup` / `load_soup` now return a `selectolax` node instead of a `BeautifulSoup` (bs4-style `.find`/`.select`/`.get_text` calls no longer work)
- **Breaking (output):** renamed the right-hand knowledge-panel rows from `type="knowledge"`/`sub_type="panel_rhs"` to `type="side_bar"` (`sub_type="panel"` for the main entity panel, `sub_type="links"` for each link box); consumers filtering on the old type must switch
- **Breaking (demos):** moved the demos into the package (`WebSearcher.demos`), run via a single `ws-demo` command (`parse|show|search|searches|headers|locations`); replaces the `demo-search`/`demo-searches` entry points
- Added `features.main_layout` to `parse_serp` output, and refactored the `standard-*` layout dispatch into a data-driven table with labels derived from the `kp-wp-tab-*` container each detects
- Added `election_dates`, `election_results`, and `election_resources` component types for whole-page election panels
- Broadened whole-page knowledge-panel (`kp-wholepage`) coverage: recovered near-empty complementary panel bodies (entity header, VisualDigest sub-results, music sections, related searches, and link boxes), parsed collapsed tabs as a sub-column to recover silently-dropped organics, and dropped the noisy "things to know" Q&A rows
- Split bare-`tF2Cxc` organic bundles in `general` into one result per organic (excluding People-Also-Ask sources)
- Optimized `get_text`, the hottest parse helper, with a native selectolax `text()` fast path (byte-identical output)
- Fixed a `no-rso` layout bug that duplicated the trailing page-level section, and `ComponentList.add_component` to honor an explicit `cmpt_rank` of `0`
- Dev tooling: emptied `scripts/` — the parse benchmark moved into the package as `WebSearcher.bench`, maintainer workflows became local `.claude/skills/`, and a tracked `tests/test_corpus_integrity.py` gates the fixture corpus in CI
- Package-wide simplification pass (dead-code removal, shared-helper reuse) with characterization tests pinning every main-layout routing and extraction branch

## [0.8.6] - 2026-05-26

- Fixed `demo_search_headers` for the `requests` method and current API, the `demo_locations` lookahead regex and multiprocessing main guard, and a demo-search Chrome-version import that broke against older installed `websearcher` versions
- Quieted Selenium teardown (direct `quit()`, muted `urllib3` retry noise)

## [0.8.5] - 2026-05-26

- Updated demo scripts, examples, and documentation
- Trimmed the published source distribution (`sdist`) from ~24MB to ~100KB by restricting it to the package, `scripts/`, and metadata (excluding `docs/`, `tests/` fixtures, and dev config); the installed wheel was already package-only, so this affects only the PyPI source archive (no runtime or `pip install` change)

## [0.8.4] - 2026-05-25

- Added a `products` component type (sub_types `grid` and `brands`) for organic shopping packs that previously slipped into `general` and emitted hollow "no title or url" rows; modern (`apg-product-result`) and older (`product-viewer-group` + `g-inner-card`) product grids now yield title, store, and a `ratings` details block, and "Explore brands" carousels yield brand title, merchant url, and store rating
- Added a `promo` component type (`sub_type="shopping"`) that captures the "Save with deals / Shop deals" banner; narrowed the extractor's `is_valid` promo-throttler guard to drop only the results-wrapper variant (carrying `div.g`) so the pure promo banner is no longer discarded
- Added a `most_read_articles` component type for the editorial article carousel (title and url per publisher card)
- Added a `buying_guide` component type for the faceted buying-guide accordion (one row per label/question facet)
- Added a `general` `sub_type="image_strip"` flag for results carrying a `g-img` thumbnail strip (Pinterest boards, Etsy markets, shop pages)
- Eliminated all remaining hollow `general` "no title or url" rows (29 -> 0 across the fixture corpus) by routing these misclassified blocks to their correct types

## [0.8.3] - 2026-05-25

- Added legacy 2024-SGE markup support to the `ai_overview` parser so historical crawls recover synthesized answer text and sources (detection already worked; content extraction returned empty against the current-DOM-only selectors)
- Added `ai_overview` `sub_type="unavailable"` to mark detected-but-declined overviews ("An AI Overview is not available for this search"), distinguishing a genuine decline from a parser miss
- Added a `recipes` parser (the component was unmapped and emitted a `<|>`-joined text blob); recipe cards now yield `title`/`url` plus a `ratings` details block (source, rating, n_reviews, duration, ingredients)
- Recovered empty `knowledge` sub_types: `featured_results` (panel text + source url), `dictionary` (headword + definitions via `data-attrid`), and `panel_rhs` (entity titles, "Things to know" topics; hollow placeholder rows dropped)
- Recovered `twitter_cards` card `title` from the tweet permalink handle on single-account carousels
- Added modern product-listing-ad support to `shopping_ads` (the `clickable-card` layout that previously emitted "no subcomponents parsed"), with price, source, and review-count details
- Backfilled README `Recent Changes` to cover `0.8.0`, `0.8.1`, and `0.8.2`

## [0.8.2] - 2026-05-24

- Reduced per-SERP `parse_serp` time ~24% (134 -> 102 ms over the fixture corpus) by replacing whole-document `str(soup)` re-serialization in feature extraction with structural lookups, gating the classifier chain on structural-signal preconditions, and trimming extraction-phase text and subtree walks
- Lazy-loaded `SearchEngine` so `import WebSearcher` no longer imports Selenium / undetected-chromedriver for parse-only use (~28% faster cold import); `WebSearcher.SearchEngine` still resolves on access
- Moved the feature extractor module to `WebSearcher.extractors.extractor_serp_features` (the public `WebSearcher.FeatureExtractor` is unchanged)
- Fixed the `is_valid` hidden-survey filter that never fired (an `"attrs" in c` guard tested child membership instead of attribute presence)
- Added `scripts/bench_parse.py` for parse benchmarking and cProfile profiling

## [0.8.1] - 2026-05-24

- **Breaking:** `ai_overview` is now a top-level component `type` (was `knowledge.sub_type=ai_overview`); new section-aware parser with `details.type="ai_overview"`, `details.sections`, and `details.sources` (publisher-labeled)
- **Breaking:** `ai_overview` `details.sources[*]` shape replaced: `{url, text}` -> `{source_id, url, title, snippet, publisher, favicon}`; `text` (publisher label) is renamed to `publisher`, and `title`/`snippet`/`favicon`/`source_id` are added from the inline payload data
- Added `citations` arrays to `ai_overview` `details.sections[*]` and `details` (lede-level): each entry is `{publisher, additional_count, source_ids}`, sourced from `button.rBl3me` widgets plus their backing payload data
- Added classifier guard so the "Related Links" sibling no longer matches `ai_overview`
- Fixed `Publisher +N` button labels leaking into `ai_overview` section text (buttons are now decomposed before text extraction)
- Bumped security floors via Dependabot: `urllib3` 2.6.3 -> 2.7.0 (cross-origin header forwarding, decompression-bomb bypass) and `idna` 3.11 -> 3.15 (IDNA encode bypass)
- Bumped dependencies via Dependabot: `requests` 2.33.0 -> 2.34.2, `protobuf` 6.33.5 -> 7.34.1, `pydantic` 2.12.5 -> 2.13.4, `polars` 1.38.1 -> 1.40.1, and `pytest-cov` 7.0.0 -> 7.1.0

## [0.8.0] - 2026-05-10

- Added `jobs` and `flights` parsers (`flights` previously emitted a "not implemented" placeholder)
- Added `videos` classifier and a `trailers-and-clips` sub_type
- Added `knowledge_subcard` classifier for entity-panel sections
- Updated `parse_ads` to capture mixed ad layouts; added ad regression fixtures
- Expanded `local_results` details with rating, price, category, address, phone, hours, and review snippet
- Captured modern `perspectives` items, including embedded tweets, via a `role=listitem` fallback
- Updated `available_on` parser and classifier for the current Google layout
- Added current-layout selectors to `searches_related` so related terms are extracted again
- Captured the modern rating widget and unblocked submenu detection in the `general` parser
- Updated knowledge-panel extraction and normalized text whitespace
- Dropped empty `video` details when both source and duration are null
- Added `scripts/show_parsed.py` (parsed-results table) and `scripts/show_serp.py` (serve saved SERP HTML locally, with `--raw`)
- Added project `CLAUDE.md` with inspection-script references and parser conventions
- Narrowed `Tag` types and standardized imports, `Selector` usage, and docstrings across the component parsers

## [0.7.1] - 2026-05-03

- Added component type registry: consolidates header-text mappings, parser dispatch, and labels (supersedes `cmpt_mappings.py`)
- Added `find_by_selectors` utility; applied to classifiers
- Added `Selector` NamedTuple in `utils` for tag/attrs selector lists
- Added pyrefly type checking; fixed all type errors across the codebase
- Added structural tests for component type registry; resolved "Ver más" collision
- Refactored ad parser and classifier; tidied carousel scope; edited local parser/classifier selectors
- Restored `knowledge_panel` cmpt-attr check on `jscontroller qTdDb`
- Moved `ClassifyHeaderText` into `main.py` as `ClassifyMainHeader`; removed dead `ClassifyHeaderComponent`
- Updated CI: ruff lint + format checks, pyrefly check, coverage; matrix narrowed to 3.12-3.14
- Switched publish workflow to tag-based with split build + publish jobs
- Added Dependabot config, PR template, pre-commit ruff + pyrefly hooks
- Bumped support floor: `requires-python = ">=3.12"`, ruff/pyrefly `target-version = py312`
- Bumped security floors: `requests>=2.33.0`, `lxml>=6.1.0`, `pytest>=9.0.3`; pulled Dependabot patches for `pygments`
- Fixed `ResponseOutput` not subscriptable for dict-style access
- Added `CHANGELOG.md` and changelog guide (migrated from README)
- Added `docs/plans/` development history with landing page

## [0.7.0] - 2026-03-15

- **Breaking:** `details` field is now always `dict | None` with a self-describing `type` key (e.g. `{"type": "menu", "items": [...]}`)
- **Breaking:** `parse_serp()` now always returns a dict with `results` and `features` keys; the `extract_features` parameter has been removed
- Standardized all models on Pydantic BaseModel (removed dataclasses)
- Added `ResponseOutput` and `ParsedSERP` typed models
- Removed `DetailsItem`, `DetailsList` classes
- Normalized `local_results` sub_type for location-specific headers
- Replaced `os` with `pathlib.Path` throughout
- Consolidated `webutils.py` into `utils.py`
- Added ruff formatting, linting, and pre-commit hooks
- Added test coverage reporting (69%)
- Added unit tests for utils, locations, models, and feature extractor
- Replaced pandas with polars in demo scripts

## [0.6.9] - 2026-02-22

- Fixed bugs in component parsers (class comparison, assignment operator, set literal)
- Fixed `return` in `finally` block in requests searcher
- Added captcha detection to feature extractor
- Added captcha handling and jittered delay to demo searches
- Dropped pandas from core dependencies
- Cleaned up legacy typing imports
- Removed poetry.toml

## [0.6.8] - 2026-02-20

- Migrated from Poetry to uv for dependency management
- Added Python 3.12-3.14 test matrix in GitHub Actions
- Added `flights` classifier and `standard-4` layout
- Added local service ad parser
- Extracted bottom ads before main column
- Fixed `return` in `finally` block warning in selenium searcher

## [0.6.7] - 2026-02-06

- Added `get_text_by_selectors()` to `webutils` -- centralizes multi-selector fallback pattern across 7 component parsers
- Added `perspectives`, `recent_posts`, and `latest_from` component classifiers
- Added `sub_type` to perspectives parser from header text
- Added CI test workflow on push to dev branch
- Added compressed test fixtures with `condense_fixtures.py` script
- Updated dependency lower bounds for security patches (protobuf, orjson)
- Updated GitHub Actions to checkout v6 and setup-python v6

## [0.6.6] - 2025-12-05

- Update packages with dependabot alerts (brotli, urllib3)

## [0.6.5] - 2025-12-05

- Add GitHub Actions section to README

## [0.6.0] - 2025-03-28

- Method for collecting data with selenium; requests no longer works without a redirect
- Pull request [#72](https://github.com/gitronald/WebSearcher/pull/72)

## [0.5.2] - 2025-03-09

- Added support for Spanish component headers by text
- Pull request [#74](https://github.com/gitronald/WebSearcher/pull/74)

## [0.5.1] - 2025-03-07

- Fixed canonical name -> UULE converter using `protobuf`, see [this gist](https://gist.github.com/gitronald/66cac42194ea2d489ff3a1e32651e736) for details
- Added lang arg to specify language in se.search, uses hl URL param and does not change Accept-Language request header (which defaults to en-US), but works in tests.
- Fixed null location/language arg input handling (again)
- Pull Request [#76](https://github.com/gitronald/WebSearcher/pull/76)

## [0.5.0] - 2025-02-03

- configuration now using poetry v2

## [0.4.9] - 2025-02-03

- last version with poetry v1, future versions (`>=0.5.0`) will use [poetry v2](https://python-poetry.org/blog/announcing-poetry-2.0.1/) configs.

## [0.4.2] - [0.4.8] - 2024-11-11 to 2025-02-03

- varied parser updates, testing with py3.12.

## [0.4.1] - 2024-08-26

- Added notices component types, including query edits, suggestions, language tips, and location tips.

## [0.4.0] - 2024-05-27

- Restructured parser for component classes, split classifier into submodules for header, main, footer, etc., and rewrote extractors to work with component classes. Various bug fixes.

## [0.3.13]

- New footer parser, broader extraction coverage, various bug and deprecation fixes.

## [0.3.12] - 2024-05-09

- Added num_results to search args, added handling for local results text and labels (made by the SE), ignore hidden_survey type at extraction.

## [0.3.11] - 2024-05-08

- Added extraction of labels for ads (made by the SE), use model validation, cleanup and various bug fixes.

## [0.3.10] - 2024-05-06

- Updated component classifier for images, added exportable header text mappings, added gist on localized searches.

## [0.3.9] - 2024-02-25

- Small fixes for video url parsing

## [0.3.8] - 2024-02-13

- Using SERP pydantic model, added github pip publishing workflow

## [0.3.7] - 2024-02-09

- Fixed localization, parser and classifier updates and fixes, image subtypes, changed rhs component handling.

## [0.3.0] - [0.3.6] - 2023-10-16 to 2023-12-08

- Parser updates for SERPs from 2022 and 2023, standalone extractors file, added pydantic, reduced redundancies in outputs.

## [2020.0.0], [2022.12.18], [2023.01.04] - 2022-12-19, 2022-12-21, and 2023-01-04

- Various updates, attempt at date versioning that seemed like a good idea at the time ¯\\\_(ツ)\_/¯

<!-- refs/tags/v2022.12.18 -->
<!-- refs/tags/v2023.01.04 -->

## [0.2.15]

- Fix people-also-ask and hotel false positives, add flag for left-hand side bar

## [0.2.14]

- Add shopping ads carousel and three knowledge subtypes (flights, hotels, events)

## [0.2.13]

- Small fixes for knowledge subtypes, general subtypes, and ads

## [0.2.12] - 2021-12-17

- Try to brotli decompress by default

## [0.2.11] - 2021-11-15

- Fixed local result parser and no return in general extra details

## [0.2.10]

- a) Add right-hand-side knowledge panel and top image carousel, b) Add knowledge and general component subtypes, c) Updates to component classifier, footer, ad, and people_also_ask components

## [0.2.9] - 2021-05-08

- Various fixes for SERPs with a left-hand side bar, which are becoming more common and change other parts of the SERP layout.

## [0.2.8] - 2021-03-08

- Small fixes due to HTML changes, such as missing titles and URLs in general components

## [0.2.7] - 2020-11-30

- Added fix for parsing twitter cards, removed pandas dependencies and several unused functions, moving towards greater package simplicity.

## [0.2.6] - 2020-11-14

- Updated ad parser for latest format, still handles older ad format.

## [0.2.5] - 2020-07-24

-  Google Search, like most online platforms, undergoes changes over time. These changes often affect not just their outward appearance, but the underlying code that parsers depend on. This makes parsing a goal with a moving target. Sometime around February 2020, Google changed a few elements of their HTML structure which broke this parser. I created this patch for these changes, but have not tested its backwards compatibility (e.g. on SERPs collected prior to 2/2020). More generally, there's no guarantee on future compatibility. In fact, there is almost certainly the opposite: more changes will inevitably occur. If you have older data that you need to parse and the current parser doesn't work, you can try using `0.2.1`, or send a pull request if you find a way to make both work!
