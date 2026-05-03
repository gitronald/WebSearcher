# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### [0.7.1a1] - 2026-05-03

- Bump security floors: `requests>=2.33.0`, `lxml>=6.1.0`, `pytest>=9.0.3`
- Pull in Dependabot patches for `requests`, `lxml`, `pygments`, and `pytest`
- Fix `ResponseOutput` not subscriptable for dict-style access
- Add `docs/plans/` development history with landing page

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
