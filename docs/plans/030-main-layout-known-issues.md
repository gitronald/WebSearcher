---
status: done
branch: claude/simplify-websearcher-pkg
created: 2026-05-30T20:42:03-07:00
completed: 2026-05-30T23:21:20-07:00
pr: https://github.com/gitronald/WebSearcher/pull/142
---

# Main-Section Layout: Known Issues & Follow-ups

## Status

Done. The implementation work described below (making
`ExtractorMain.layout_label` observable, pinning every layout branch,
refactoring the `standard-*` ladder, renaming the labels) landed in PR #142,
merged into `feature/v0.9.0`. The "Open issues" section records deferred layout
problems that were intentionally not changed — they touch extraction branches
no fixture exercises — and stands as the historical follow-up record.

What landed in #142:

- `features.main_layout` exposes the main-section layout label in parsed output.
- Characterization pins in `tests/test_extractor_main.py` cover every observable
  `layout_label` outcome (the SERP fixtures only witness `standard`,
  `standard-overview`, `standard-airfares`).
- `extract_from_standard` / `_extract_from_standard_sub_type` collapsed into a
  `_StandardLayout` table + two extraction shapes.
- `no-rso` `sec2` duplication bug fixed (was appended once per `sec1` div).
- `standard-N` renamed to observable, `kp-wp-tab-*`-derived names
  (`standard-overview`/`-songs`/`-sports-standings`/`-airfares`) and the
  bolted-on fallback renamed `standard-fallback`.

This doc tracks what was deliberately **not** changed, because the fixes touch
extraction branches no fixture exercises and would be guesses without a real
witnessed SERP.

## Layout label inventory

Routing keys (`get_layout` -> `layout_extractors`): `standard`, `top-bars`,
`left-bar`, `no-rso`. Final observable values after extractor mutation:

| Value | Witnessed in fixtures |
|---|---|
| `standard` | yes (62) |
| `standard-overview` | yes (3) |
| `standard-airfares` | yes (1) |
| `standard-songs` | no (pinned synthetically) |
| `standard-sports-standings` | no (pinned synthetically) |
| `standard-fallback` | no (pinned synthetically) |
| `top-bars-divs` | no |
| `top-bars-children` | no |
| `left-bar` | no |
| `no-rso` | no (extraction path pinned synthetically) |

`top-bars` is never a final value (always mutates to `-divs`/`-children`).
`None` is unreachable from `get_layout`.

## Open issues

### 1. `left-bar` extraction is scoped to the whole document

`extract_from_left_bar` returns `subtree_css(self.soup, "div.TzHB6b")` over the
entire page, ignoring `layout_divs["left-bar"]` (the `div.OeVqAd` it detected
on). `div.TzHB6b` is **not** a left-bar marker -- it is a generic knowledge-panel
container also keyed on by `standard-overview`, the `standard-fallback` path, and
the RHS knowledge-panel detector (`extractor_rhs.py`). So detection and
extraction target unrelated things, and extraction reaches across sections.

- **Faithful port, not a regression.** Git history shows the bs4 original was
  literally `self.soup.find_all("div", {"class": "TzHB6b"})` -- document-wide
  from the start.
- **Likely benign today:** the registry is 1:1 (in a `left-bar` layout, this is
  the only main extractor that runs, so there is no second pass to duplicate
  against), and RHS panels are `remove()`d from the tree before main extraction,
  so the cross-section bleed is largely closed in the full pipeline. The unit
  pin (`test_left_bar_extracts_tzhb6b_document_wide`) documents the raw
  document-wide reach in isolation.
- **Why deferred:** zero `left-bar` fixtures. Narrowing the scope to
  `subtree_css(left_bar_div, "div.TzHB6b")` could just as easily break a real
  left-bar SERP as fix one, with no witness either way.
- **To resolve:** capture a real `left-bar` SERP, snapshot it, then decide
  scope as a one-line, fully-witnessed change.

### 2. `standard-fallback` extraction body is effectively dead

The fallback re-targets the same `kp-wp-tab-overview` + `TzHB6b`/`A6K0A` that
`standard-overview` already gates on and checks first. Any content the fallback
could find, `standard-overview` already caught -- so the label only persists on
an essentially empty `rso`, with its extraction body unreachable (consistent
with 0 fixtures and the pin asserting an empty result).

- **To resolve:** confirm against a witnessed empty-`rso` SERP, then either drop
  the dead extraction body (keep the label as a pure "nothing extracted" signal)
  or delete the branch entirely if the label has no consumer value.

### 3. `left-bar` / `top-bars` shadow a populated `rso`

In `get_layout`, when a `left-bar` (or populated `top-bars` with no rso) is
present, the label resolves away from `standard` and `rso` is never read. A page
carrying both a left-bar/top-bars marker **and** a populated `rso` would drop the
`rso` results. Whether that combination occurs in the wild is unknown (no
fixture). The routing truth table is pinned in `test_extractor_main.py`
(`test_get_layout_label_*`), so the current precedence is at least locked.

### 4. `layout_label` has a dual role (routing key + result descriptor)

`layout_label` is both the dispatch key (`get_layout` -> `layout_extractors`)
and the mutated result descriptor (`standard-*`, `top-bars-*`). The mapping is
not 1:1 (`standard` -> 6 outcomes, `top-bars` -> 2), and the registry is keyed
on the pre-mutation value while output reports the post-mutation one. The table
refactor reduced the fragility on the `standard-*` side, but the split between a
routing key and an output label remains implicit. A future cleanup could split
these into two fields (a `routing` enum and an observable `main_layout`) if the
output value ever needs a stable, documented set.

### 5. Dead defensive code in `_main_column`

Both `if self.layout_label is None: raise ValueError(...)` and the
`KeyError -> ValueError("no extractor...")` are unreachable: `get_layout` always
assigns one of the four registered routing keys. Low priority; safe to drop if
touching this method for another reason.

## Dependencies

Issues 1-3 are blocked on capturing witnessed fixtures for the unexercised
layouts (`left-bar`, empty-`rso`, left-bar-or-top-bars + populated `rso`). Issues
4-5 are pure cleanups with no blocker, but low value on their own.
