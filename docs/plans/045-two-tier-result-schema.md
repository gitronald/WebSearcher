---
status: done
branch: claude/session-context-ERiTn
created: 2026-06-07T12:41:01-07:00
completed: 2026-06-08T00:42:43-07:00
pr: https://github.com/gitronald/WebSearcher/pull/164
---

# Two-tier result schema: lean core + a `details` extras bucket

## Plan

### Motivation

A parsed result row currently mixes three kinds of field at the top level: core "what / where / what-it-says" content (`type`, `sub_type`, `title`, `url`, `text`, `cite`, `sub_rank`, plus pipeline-added `section` / `cmpt_rank` / `serp_rank`), the typed content payload (`details`), and a parse-status diagnostic (`error`). For the common use case — "what results did the user see, in what order" — `error` is dead weight (null on every successful row), and the row-level `visible` / `timestamp` metadata (plan 018) don't belong at the top level either.

This plan formalizes a **two-tier schema**: a lean *core* tier for the common case, and `details` as the *extras* bucket — component-specific payload, render metadata, and diagnostics that matter for digging into specific components or debugging, but not for most analyses.

### The split (decided)

- **Stays core (top-level):** `type`, `sub_type`, `title`, `url`, `text`, `cite`, `sub_rank`, plus pipeline-added `section`, `cmpt_rank`, `serp_rank`. `cite` stays core **deliberately** — it's the visible source the user saw, a peer of `title`/`url`/`text`, and the "what did the user see" framing that motivated `visible` wants it. (Only `error` moves; `cite` was explicitly ruled out.)
- **Moves into `details`:** `error` (parse-status diagnostic), plus `visible` and `timestamp` (row-level render metadata — already headed there in plan 018's working tree).

### Key upside — this resolves plan 018's idiom friction

`details` is sparse today (often `None`), which is exactly what made writing `visible`/`timestamp` into it awkward — every idiom needed a get-or-create dance (`set_visible`, `set_item_visible({...})`, `card_details(parsed)[k]=v`), all rejected as obscure (see plan 018's 2026-06-07 log). Once `details` also carries `error` and is therefore present on far more rows, the "fabricate a dict just for metadata" problem largely dissolves: rows **build `details` once at construction** with every field a literal key (plan 018's "Option B"), and the `card_details` helper goes away. So the broader schema direction *picks* Option B.

### Decisions (resolved 2026-06-08)

1. **One `details` dict, or a nested `meta`?** → **Single dict, sibling keys.** `error`/`visible`/`timestamp` ride as siblings next to the content `type`/payload (`{"type": "hyperlinks", "items": [...], "visible": false, "timestamp": "2h"}`), documented as *reserved metadata keys* understood independently of the `type` content discriminator. Consistent with the existing `details["items"][]["visible"]` precedent on 018's branch.
2. **`details` always carries a `type` — generic `"item"` when there's no specialized payload.** → A content row keeps its specific content `type` (`"ratings"`, `"hyperlinks"`, …) with metadata as siblings. A **metadata-only** `details` (an error-only row, or a `visible`/`timestamp`-only row) gets **`type: "item"`** so `details["type"]` is *always present* and consumers can switch on it without a None-check. No fake `{"type": "error"}` label. (Supersedes the earlier "no `type` key" lean.)
3. **Keep "None when it adds no info"?** → **Yes, only-when-present.** Record `error` only when non-null, `visible` only when `False`, `timestamp` only when present. A clean row's `details` stays `None`. Mirrors the only-when-hidden idiom and bounds the snapshot diff.
4. **Version cut.** → **v0.10.0** (current `feature/v0.10.0` cycle). 0.9.0 already shipped breaking changes, so a BREAKING entry here fits the cadence; no reason to defer to 0.11.0.
5. **Scope of this pass.** → **Full scope:** `error` + `visible` + `timestamp`, in one coherent migration.
6. **`error` handling (Option B + cleanups).** → **Move `error` into `details`, preserving the full message set** (relocated, not dropped), recorded only-when-present per decision #3. Chosen over keeping it top-level (avoids the null-on-every-clean-row "dead weight") and over dropping it (Option C would discard the categorical messages and gut the `test_no_parse_errors` canary, which is `error`'s *only* consumer). Plus two cleanups, applied regardless:
   - **Drop the redundant `general.py` `"no title or url"`** — fully equivalent to `title is None and url is None`, already covered by `test_general_results_have_title_or_url`.
   - **Close the error vocabulary** — collapse the duplicate `"No subcomponents found"` (videos/top_stories) and `"no subcomponents parsed"` (components) into one message; define a small closed set of error strings (same discipline as plan 034's `sub_type` closed set), so the canary's allowlist is exhaustive.

### Findings from grounding the plan in the current tree (2026-06-08)

- **`error` is written in SIX sites** (the plan originally captured two), all of which must migrate in lockstep — in two categories:
  - *Component-level* (`components.py::create_parsed_list_error`): `not implemented`, `null component type`, `parser output not list or dict`, `no subcomponents parsed`, `parsing exception: <traceback>`. Diagnostic-only rows (no content payload) → `details = {"type": "item", "error": ...}`.
  - *Parser-internal*: `general.py:98` `"no title or url"` (**to be dropped** — redundant); `videos.py:47` & `top_stories.py:39` `"No subcomponents found"` (**normalize** with `no subcomponents parsed`); `locations.py:18` `f"unknown sub_type: {sub_type}"` and `locations.py:51` `"no hotel items found"`.
- **`error` has NO in-repo consumer except the test suite.** Nothing in the package, demos, or any in-repo caller reads a row's `error`; it is written by the six sites and read only by `test_no_parse_errors` (the regression canary, via the `KNOWN_ERRORS` allowlist), `test_general_results_have_title_or_url` (skips error rows), and ~9 `assert r["error"] is None` coverage checks. The plan's "downstream consumers break" worry is therefore in-repo a non-issue (external consumers unknown). This is *why* Option B (preserve the messages) beats Option C (drop them): the canary is the field's sole purpose.
- **Silent-drop hazard.** `BaseResult` sets no `model_config`, so pydantic v2 `extra="ignore"` applies. Once `error` leaves `BaseResult`, any leftover top-level `error=` kwarg in the round-trip (`BaseResult(**row).model_dump()`) is **silently discarded**, not flagged — and *no test catches it* (a dropped error reads as "no errors = green"). Mitigation: temporarily set `model_config = ConfigDict(extra="forbid")` on `BaseResult` during the cutover so a missed site *raises*, then relax it. All six sites must move `error` into `details` in the same change.
- **`general.py` error coexists with a content `details`.** `general.py` builds its content `details` in `parse_subtype_details` (e.g. `{"type": "ratings", ...}`); when the `"no title or url"` guard also fires (pre-cleanup), the error must merge into *that* dict, not a fresh one. (Moot once the redundant message is dropped, but the same merge pattern applies to any future content-row error.)
- **018 carryforward — what actually exists in git** (branch `origin/feature/v0.10.0-visible-flag`, PR #160):
  - `_slx.py::is_hidden` — committed, clean, **reuse as-is**.
  - top-level `visible: bool` field + row-level and `details["items"][]`-level `visible` writes in `footer`/`videos`/`top_image_carousel`/`short_videos`/`top_stories`/`available_on`/`shopping_ads` — committed; relocate from top-level into `details`.
  - ⚠️ **The "uncommitted Option-C" timestamp rescue and `check_is_visible`/`tests/test_card_details.py` are NOT in git** — they existed only in a working tree. `check_is_visible` exists nowhere in the repo. The `timestamp` extraction across `news_quotes`/`twitter_result`/`view_more_news`/`videos` must be **rebuilt from scratch**, not cherry-picked. This is the largest scoping uncertainty.
- **Premise check:** `details` is `None` on the bulk of rows (general organics); 21 parsers / 46 sites build it. The friction the plan says "dissolves" actually *shrinks to the minority* — a hidden general organic with no content still fabricates `{"visible": false}`. Option-B inline construction handles it cleanly; just not literally zero.

### Blast radius (breaking change)

- **`BaseResult`** (`WebSearcher/models/data.py`): remove the top-level `error` field; update the `details` description. (`visible`/`timestamp` were never top-level fields after 018's rework.)
- **`components.py` round-trip** (`BaseResult(**row).model_dump()`): `error` no longer a top-level key — confirm nothing in the pipeline relies on it there.
- **Tests:** `test_no_parse_errors` reads `r["error"]` → must read the details-nested error; `EXPECTED_KEYS` in `test_parse_serp.py` drops `error`; `test_field_types`; all 87 snapshots regenerate.
- **Downstream consumers** use dict-style access on result rows (`r["error"]`, etc.); relocating `error` breaks them. Needs a CHANGELOG **BREAKING** entry and a migration note (and possibly a deprecation window).

### Relationship to plan 018

Plan 018 (the `visible` flag) is the seed of this idea and has been **retired and folded into this plan** — its 2026-06-07 log documents the back-and-forth (where row metadata lives, and how it's written into `details`) that revealed the question is really *schema*-shaped, not visible-flag-shaped. So **this plan now owns the full scope**: `visible`, `timestamp`, *and* `error`, placed in `details` in one coherent migration. The `visible` flag ships here, not under 018.

What carries forward from 018's branch (`feature/v0.10.0-visible-flag`, PR #160, to be closed unmerged):

- **Reuse as-is:** `is_hidden` (`WebSearcher/_slx.py`) — the one committed detection primitive. (`check_is_visible` does *not* exist anywhere in git; it was working-tree-only and is gone.)
- **Starting point:** the committed top-level `visible` field + the row-/item-level `visible` writes in 7 parsers (relocate top-level → `details`). The Option-C redesign (the `timestamp` rescue across `news_quotes`/`twitter_result`/`view_more_news`/`videos`, `tests/test_card_details.py`) was **never committed and is unrecoverable** — rebuild the `timestamp` extraction from scratch; use Option-B inline construction throughout (no `card_details` helper).

### Implementation order (resolved — two phases, A shippable on its own)

**Phase A — relocate `error` into `details` (self-contained, fully recoverable from current code):**

1. `models/data.py`: remove the top-level `error` field; document on `details` the reserved metadata keys (`error`, `visible`, `timestamp`) and the **`type: "item"` for metadata-only** convention. Add `model_config = ConfigDict(extra="forbid")` **temporarily** as a migration guard (relax at the end).
2. Define the **closed error vocabulary** (one module-level constant) and route all six write sites through `details`:
   - `components.py::create_parsed_list_error` → `details = {"type": "item", "error": ...}` (build once, literal keys); normalize `no subcomponents parsed`.
   - `videos.py:47`, `top_stories.py:39` → `{"type": "item", "error": <normalized "no subcomponents parsed">}`.
   - `locations.py:18/51` → `{"type": "item", "error": ...}`.
   - `general.py:98` → **delete** the `"no title or url"` assignment (redundant cleanup).
3. Tests: drop `error` from `EXPECTED_KEYS`; point `test_no_parse_errors` (`test_parse_serp.py:136`) and `test_field_types` (`:177`) at `r["details"]`; update `KNOWN_ERRORS` to the closed vocabulary (and drop `"no title or url"` / `"No subcomponents found"`); fix `test_components.py:23/35`, `test_models.py:172`, `test_general_results_have_title_or_url` (no longer gated on `error`), and the ~9 `r["error"] is None` asserts in `test_parser_coverage.py`.
4. Relax the `extra="forbid"` guard back to default; regenerate snapshots; verify the diff is bounded to `error`→`details` (plus the dropped/normalized messages).

**Phase B — fold in `visible` + `timestamp`:**

5. Cherry-pick `_slx.py::is_hidden` from `feature/v0.10.0-visible-flag` as-is.
6. Re-apply row-level + `details["items"][]`-level `visible` writes into `details` (only-when-`False`, Option B; metadata-only rows get `type: "item"`), across `footer`/`videos`/`top_image_carousel`/`short_videos`/`top_stories`/`available_on`/`shopping_ads`.
7. **Rebuild** the lost `timestamp` extraction (net-new, not a cherry-pick) across `news_quotes`/`twitter_result`/`view_more_news`/`videos`; write into the same per-row `details`.
8. Regenerate snapshots; verify the diff is bounded to `visible`/`timestamp`/`details`.

**Wrap-up:** CHANGELOG **BREAKING** entry + downstream migration note (`r["error"]` → `r["details"]["error"]`); README recent-changes; refresh `docs/README.md` plan table.

### Out of scope

- Moving `cite` (explicitly kept core).
- Other silently-dropped top-level keys found nearby (e.g. `view_more_news` sets a top-level `img_url` that the round-trip drops) — separate follow-ups, though they could ride this migration if convenient.

## Log

### 2026-06-08 — Phase A complete (error relocation + cleanups)

`error` is off the top level and lives in `details`; **Phase B (`visible`/`timestamp`) not yet started.**

- `models/data.py`: removed the `error` field; documented the two-tier schema + `type:"item"` invariant on `BaseResult.details`; added the closed error vocabulary (`ERR_*` constants) and an `error_details(error)` helper (`{"type": "item", "error": ...}`).
- Migrated all **six** write sites through `error_details`: `components.py::create_parsed_list_error` (also dropped its dead `cmpt_rank` key, re-added downstream by `export_results`) and the five `ERR_*` call sites in `components.py`; `videos.py`, `top_stories.py` (both → `ERR_NO_SUBCOMPONENTS`, normalizing `"No subcomponents found"`); `locations.py` (×2). Deleted `general.py`'s redundant `"no title or url"`.
- Tests: dropped `error` from `EXPECTED_KEYS`; `KNOWN_ERRORS = {ERR_NOT_IMPLEMENTED, ERR_NO_SUBCOMPONENTS}`; added a `_row_error(r)` helper in `test_parse_serp.py`/`test_parser_coverage.py`; updated `test_no_parse_errors`, `test_field_types`, `test_general_results_have_title_or_url`, `test_components.py` (×2), `test_models.py`.
- Snapshots regenerated; diff is exactly bounded — 2267 top-level `"error": null` removed, the 3 real error rows moved into `details` as `{"type": "item", "error": "no subcomponents parsed"}`.
- Verified: full suite **457 passed, 87 snapshots**; `ruff check` clean; `ruff format` applied.
- Silent-drop guard: confirmed via grep that no top-level `error=` kwarg remains at any write site (rather than committing a temporary `extra="forbid"`).

### 2026-06-08 — Phase B complete (visible + timestamp)

Full scope shipped. `error`, `visible`, and `timestamp` all live in `details`.

- **`visible`** (commit "Phase B part 1"): cherry-picked `_slx.is_hidden` as-is; added `_common.mark_hidden_row` / `mark_hidden_item` (record `visible=False` only-when-hidden). Applied at the row level (`videos`, `top_stories`, `short_videos`, `shopping_ads` ×3, `footer` img-card) and the `details["items"]` level (`top_image_carousel`, `available_on` ×2, `footer` images).
- **Type invariant discovery + resolution:** found the "`details` always has a type" claim was already false — `perspectives` (377, `heading`), `knowledge` (32, `featured_results`), `locations` (9, `hotels` ratings) emit typeless content-details. Per the decision *"always have a type unless that would be the only key,"* enforced it centrally with a `BaseResult` `model_validator` that backfills `type:"item"` onto any non-empty typeless `details` (never fabricates a type-only dict). Snapshot diff bounded: +418 `type:"item"`, +42 `visible:false` (hidden perspectives), rest trailing-comma artifacts.
- **`timestamp`** (this commit): the lost extraction turned out to be mostly *recoverable* — `news_quotes`, `twitter_result`, `view_more_news` already extracted a timestamp but wrote it to a top-level key the round-trip dropped; `videos` discarded its `_timestamp`. Added `_common.mark_timestamp_row` (only-when-present) and routed all four into `details` (merging alongside `twitter_result`'s tweet payload). **Corpus gap:** none of these timestamp paths are exercised by the fixture corpus (`news_quotes`/`twitter_result`/`view_more_news` absent; corpus `videos` don't use the `zECGdd` citetime layout), so timestamp produces **zero snapshot change** — pinned instead by synthetic-markup unit tests in `tests/test_timestamp.py` (4 tests, one per parser).
- Verified: full suite **461 passed, 87 snapshots**; `ruff` clean.

### Out-of-scope follow-ups surfaced

- `view_more_news` still sets a top-level `img_url` the round-trip drops (noted in original out-of-scope; not addressed).
- `knowledge`/`locations` content-details are now generically `type:"item"`; giving them semantic types (e.g. `locations` hotels are ratings-shaped) is a possible refinement.

### 2026-06-08 — Wrap-up (img_url, schema tests, docs)

Closing-pass work after Phase B, on PR #164 (branch `claude/session-context-ERiTn`):

- **`view_more_news` `img_url`** (the out-of-scope follow-up above): addressed after all — routed into `details["img_url"]` (recorded only when present), the same dropped-top-level-key fix as `timestamp`. Pinned by synthetic-markup tests, since the corpus has no `view_more_news` rows.
- **Type-checker fix:** `mark_hidden_row` built `{"type": "item"}` (inferred `dict[str, str]`), so `details["visible"] = False` tripped `pyrefly`; rebuilt as a single heterogeneous literal `{"type": "item", "visible": False}`. The branch HEAD had been failing the `pyrefly` pre-commit hook.
- **Schema contract tests** (`tests/test_details_schema.py`, 14): pin the two-tier `details` contract — `None` on a clean row, the top level limited to core fields, the `type:"item"` backfill, only-when-informative recording of `error`/`visible`/`timestamp`, and nested item-level `visible`.
- **Docs:** README gained a "Result schema" subsection and dropped the stale top-level `error: None` from its example; CHANGELOG `[Unreleased]` got the two-tier bullets plus the cycle's `local_results` sub_type and structural-dispatch entries (via /update-docs).

**Review follow-up (close gate):** ran `/code-review` at high effort over `feature/v0.10.0...HEAD` (4 finder angles), posted to PR #164. No actionable correctness bugs. Disposition: the `general.py` "no title or url" drop and the breaking `error` relocation are documented design decisions; the hollow-payload edges in `shopping_ads._parse_sponsored_hotel` / `footer.parse_img_card` are pre-existing and out of scope; the helper-unification / fold-at-boundary / ordering-contract cleanups were consciously declined this cycle in favor of writing metadata directly into `details` at the parser (fix-at-source).

## Retrospective

- **Phase A landed exactly as specced; Phase B's `timestamp` was easier than feared.** The plan flagged the lost Option-C `timestamp` rescue as the "largest scoping uncertainty" and budgeted a from-scratch rebuild — but three of four parsers already extracted a timestamp and merely wrote it to a dropped top-level key, so the fix was a one-line reroute per parser, not a rebuild.
- **The `details`-always-has-a-`type` premise was false on arrival** (`perspectives`/`knowledge`/`locations` emit typeless content). Enforcing it centrally with one `BaseResult` validator (backfill `type:"item"`, never fabricate a type-only dict) was cleaner than patching each parser and bounded the snapshot diff.
- **The reserved-metadata mechanism churned hard and reverted.** A mid-cycle attempt to fold `error`/`visible`/`timestamp` at the `BaseResult` boundary (transient `exclude=True` fields) was rejected as over-engineering — it re-added the very top-level keys the plan removed. Final shape: parsers write straight into `details` where the value is computed. The model boundary is tempting for "uniform handling," but it fought the plan's own goal.
- **Corpus blind spots needed synthetic tests.** `timestamp` (4 parsers) and `img_url` (`view_more_news`) have zero fixture coverage, so they produce no snapshot signal — they're pinned only by `tests/test_timestamp.py`. A future regression there is invisible to the 87-snapshot suite.
- **`error` had exactly one in-repo consumer (the test canary),** which made the breaking relocation safe to do in one pass — but external dict-style consumers (`r["error"]`) break with no shim, so the CHANGELOG migration note carries the weight.
