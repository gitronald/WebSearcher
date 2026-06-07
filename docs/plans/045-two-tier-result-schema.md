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

### Decisions to make

1. **One `details` dict, or a nested `meta`?** Either everything rides as sibling keys on the single `details` dict (`{"type": "hyperlinks", "items": [...], "error": null, "visible": false, "timestamp": "2h"}`) — simple, and consistent with how `visible`/`timestamp` already ride, but the `type` discriminator then describes only the *content* payload, not the metadata keys — or split content vs metadata into `details` + a `details.meta` (or a separate top-level `meta`) sub-dict. **Lean:** single dict, sibling keys, unless the content/metadata mixing proves confusing in practice.
2. **`error` when there's no content.** An errored row has no content payload; its details would be a diagnostic-only dict. Decide the type label — reuse `card`, or a dedicated `{"type": "error", "error": "..."}`.
3. **Keep "None when it adds no info"?** `error` is null on most rows. Emitting `details.error: null` everywhere reintroduces the bloat the `visible` work fought. Likely rule: only record `error` in details when it is non-null (mirrors only-when-hidden), so a clean row's `details` stays `None`/content-only.
4. **Version cut.** This is breaking — decide whether it lands in the v0.10.0 cycle or warrants v0.11.0.

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

### Implementation order (draft)

1. Resolve the open decisions above (single dict vs `meta`; error-only type label; only-when-present rule; version cut).
2. Move `error` into `details`; update `BaseResult`, `components.py`, `EXPECTED_KEYS`, `test_no_parse_errors`.
3. Fold `visible`/`timestamp` into the same per-row `details` construction (Option B — build once, literal keys, delete `card_details`).
4. Regenerate snapshots; verify the diff is bounded to `error`/`visible`/`timestamp`/`details`.
5. CHANGELOG **BREAKING** entry + downstream migration note; README recent-changes.

### Out of scope

- Moving `cite` (explicitly kept core).
- Other silently-dropped top-level keys found nearby (e.g. `view_more_news` sets a top-level `img_url` that the round-trip drops) — separate follow-ups, though they could ride this migration if convenient.
