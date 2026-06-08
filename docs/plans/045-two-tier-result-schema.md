---
status: draft
branch:
created: 2026-06-07T12:41:01-07:00
completed:
pr:
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
2. **`error` when there's no content.** → **No `type` key for metadata-only details.** The row keeps its component `type` at the top level; its `details` is just `{"error": "..."}`. The *absence* of `details["type"]` is the signal "no content payload" — no fake `{"type": "error"}` label invented.
3. **Keep "None when it adds no info"?** → **Yes, only-when-present.** Record `error` only when non-null, `visible` only when `False`, `timestamp` only when present. A clean row's `details` stays `None` (or content-only). Mirrors the only-when-hidden idiom and bounds the snapshot diff.
4. **Version cut.** → **v0.10.0** (current `feature/v0.10.0` cycle). 0.9.0 already shipped breaking changes, so a BREAKING entry here fits the cadence; no reason to defer to 0.11.0.
5. **Scope of this pass.** → **Full scope:** `error` + `visible` + `timestamp`, in one coherent migration.

### Findings from grounding the plan in the current tree (2026-06-08)

- **`error` is written in exactly two sites**, both of which must migrate in lockstep:
  - `components.py::create_parsed_list_error` (the four component-level failures: `not implemented`, `null component type`, `parsing exception`, `no subcomponents parsed`) — these rows are diagnostic-only (`{type, cmpt_rank, text, error}`, no content).
  - `general.py:98` `parsed["error"] = "no title or url"` — set on a row that *does* carry content, confirming decision #2's "error can coexist with content" framing.
- **Silent-drop hazard.** `BaseResult` sets no `model_config`, so pydantic v2 `extra="ignore"` applies. Once `error` leaves `BaseResult`, any leftover top-level `error=` kwarg in the round-trip (`BaseResult(**row).model_dump()`) is **silently discarded**, not flagged. Both write sites above must move `error` into `details` in the *same* change or the diagnostic vanishes without a test failure.
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

- **Reuse as-is:** `is_hidden` (`WebSearcher/_slx.py`) and `check_is_visible` (`component_parsers/_common.py`) — the detection primitives, unchanged.
- **Starting point:** the committed top-level `visible` field + 87 refreshed snapshots, and the uncommitted Option-C redesign (the `timestamp` rescue across `news_quotes`/`twitter_result`/`view_more_news`/`videos`, `tests/test_card_details.py`). Cherry-pick the timestamp-extraction and tests; replace the `card_details` get-or-create with Option-B inline construction.

### Implementation order (resolved — two phases, A shippable on its own)

**Phase A — relocate `error` into `details` (self-contained, fully recoverable from current code):**

1. `models/data.py`: remove the top-level `error` field; update the `details` description to document the reserved metadata keys (`error`, `visible`, `timestamp`) and the "no `type` key ⇒ metadata-only" convention.
2. `components.py::create_parsed_list_error`: emit `{"details": {"error": ...}}` instead of a top-level `error` (build the details dict once, literal keys).
3. `general.py:98`: write the `"no title or url"` error into `details` (Option B inline) rather than `parsed["error"]`.
4. Tests: drop `error` from `EXPECTED_KEYS`; point `test_no_parse_errors` (`test_parse_serp.py:136`) and `test_field_types` (`:177`) at the nested `details` error; fix `test_components.py:23/35`, `test_models.py:172`, and the ~9 `r["error"] is None` asserts in `test_parser_coverage.py`.
5. Regenerate snapshots; verify the diff is bounded to `error`→`details`.

**Phase B — fold in `visible` + `timestamp`:**

6. Cherry-pick `_slx.py::is_hidden` from `feature/v0.10.0-visible-flag` as-is.
7. Re-apply row-level + `details["items"][]`-level `visible` writes into `details` (only-when-`False`, Option B), across `footer`/`videos`/`top_image_carousel`/`short_videos`/`top_stories`/`available_on`/`shopping_ads`.
8. **Rebuild** the lost `timestamp` extraction (net-new, not a cherry-pick) across `news_quotes`/`twitter_result`/`view_more_news`/`videos`; write into the same per-row `details`.
9. Regenerate snapshots; verify the diff is bounded to `visible`/`timestamp`/`details`.

**Wrap-up:** CHANGELOG **BREAKING** entry + downstream migration note (`r["error"]` → `r["details"]["error"]`); README recent-changes; refresh `docs/README.md` plan table.

### Out of scope

- Moving `cite` (explicitly kept core).
- Other silently-dropped top-level keys found nearby (e.g. `view_more_news` sets a top-level `img_url` that the round-trip drops) — separate follow-ups, though they could ride this migration if convenient.
