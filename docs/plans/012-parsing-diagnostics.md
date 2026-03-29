---
status: done
branch: update/extractor-position-tracking
created: 2026-02-22T12:56:12-08:00
completed: 2026-02-06T13:27:34-08:00
pr: https://github.com/gitronald/WebSearcher/pull/95
---

# Parsing Diagnostics

Improvements to make the extraction-classification-parsing pipeline easier to debug and maintain.

## 1. Classification Tracing

Add trace support to `ClassifyMain.classify` that records which classifier matched.

**Files:** `WebSearcher/classifiers/main.py`, `WebSearcher/components.py`

**Changes:**
- `ClassifyMain.classify(cmpt, trace=False)` — when `trace=True`, return a tuple `(type, classifier_name)` instead of just `type`
- `Component.classify_component()` — store the trace in `self._classifier_name` when available
- Expose via `Component` so diagnostic tools can access it

## 2. Selector Coverage Report

A test utility that checks which parser selectors actually match components across fixtures. Flags dead selectors and catches regressions where a selector stops matching.

**Files:** new `tests/test_selector_coverage.py`

**Approach:**
- Define a registry of selectors per parser (e.g., `top_stories` uses `g-inner-card`, `qmv19b`, `IJl0Z`, `JJZKK`, `WlydOe`)
- Run all fixture SERPs through extraction + classification
- For each classified component, check which of its parser's selectors match
- Report: alive selectors (matched at least once), dead selectors (zero matches)
- Could be a standalone script or a pytest with `--verbose` output

## 3. `parse_serp` Diagnostic Mode

Add a `debug=True` flag to `parse_serp` that includes pipeline metadata in each result dict.

**Files:** `WebSearcher/parsers.py`, `WebSearcher/components.py`

**Changes:**
- `parse_serp(html, debug=True)` passes debug flag through the pipeline
- Each result dict gets additional underscore-prefixed keys:
  - `_classifier`: name of the classifier that matched (e.g., `"locations"`, `"header_text:top_stories"`)
  - `_layout`: page layout label (e.g., `"standard"`, `"standard-0"`, `"top-bars"`)
  - `_section`: extraction section (e.g., `"main"`, `"header"`, `"footer"`)
- Underscore prefix keeps them out of snapshot comparisons
- Stripped from output when `debug=False` (default)

## Debugging Workflow

Reference workflow from the "cheap flights" extraction fix (see `014-dom-position-reorder.md`):

1. Scan all demo SERPs for anomalies — look for unexpectedly low result counts or missing sections (e.g. only ads, no footer)
2. Write the HTML from serps.json and take a screenshot to see what the page actually contains
3. Trace the extractor: check layout detection, what `extract_children` returns, and which components pass `is_valid`
4. Identify why components are dropped — e.g. `is_valid` rejected a wrapper because a nested element was still in the DOM
5. Fix extraction order or layout detection
6. Re-parse and compare output to the screenshot — iterate until all visible components are accounted for
7. Check classifier output for misclassifications
8. Add classifier with specific selector — test against all fixtures to avoid overly broad matches
9. Run full test suite after each change — catch regressions early
10. Update snapshots only for legitimate changes
