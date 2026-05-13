---
status: draft
branch: feature/ai-overview-payload-citations
created: 2026-05-13T13:09:20-07:00
completed:
pr:
---

# Enrich AI overview with payload-sourced citations and richer sources

## Plan

Combine the two open follow-ups from plan 021 — section/lede citation buttons (`button.rBl3me`) and richer source cards — into one effort, since both feed off the same payload data that Google embeds alongside the rendered AI overview.

### Background

When the AI overview renders, each section (and the lede) ends in a small `button.rBl3me` citation widget keyed by `data-icl-uuid`. The sources tray (`ul.bTFeG > li.CyMdWb`) carries a stable `data-src-id` per entry. The static HTML also carries machine-readable payload data per UUID, in two delivery forms:

- HTML comments: `<!--TgQPHd|[...]-->` (with `|` separator) or `<!--Sv6Kpe[...]-->` (no separator). 97% of button-bearing SERPs.
- JS data pushes: `(j.lDPB=j.lDPB||[]).push([["<jsid>","<escaped-json>"]])`. 3% of SERPs fall back to this form.

Each UUID has multiple payloads of three shapes:

- **Header** (one per button): `[[null, null, <uuid>, null, null, 1, 0, <favicon>, <publisher>, <total_count>]]`
- **Type A** (one per cited source): `[[<uuid>, [<title>, <snippet>, <favicon>, <domain>, [<publisher>], <full_url>, null, null, "<data-src-id>", ...]]]` — note `data-src-id` is at inner-array index 8 when present.
- **Type B** (indexed URL): `[[<uuid>, "<index>", 0, <full_url>, <favicon>, ""]]` — used when full Type-A data isn't echoed for that source.

Validation evidence (81-SERP / 452-button audit across the 7 demo datasets):

- 143/143 attributed buttons have payload data — 100% coverage.
- 98/143 (69%) match exactly by source-id count vs. `header.total`.
- 45/143 (31%) partial — fewer resolved `data-src-id`s than the header claims, because some cited URLs aren't in the inline `bTFeG` tray. Payloads still carry `title` / `snippet` / `full_url` for those, so we emit them as standalone citations rather than dropping.
- 142/309 (46%) unattributed `View related links` buttons also carry citation data. The other 167 are panel-open widgets with no specific list — these can stay structureless or be dropped silently.

### Implementation pieces

**1. Payload extraction module** (new file, e.g., `WebSearcher/component_parsers/_ai_overview_payloads.py`)

Regex-scan the raw HTML string (not the bs4 tree — comments are stripped from our typical traversals) for:

- `<!--TgQPHd\|(\[.*?\])-->`
- `<!--Sv6Kpe(\[.*?\])-->`
- `\["[a-zA-Z0-9_]+","(\[\[\\?"[0-9a-f-]{36}\\?".*?\]\])"\]` for the `lDPB.push` fallback (note the unicode-escape pass before `json.loads`).

JSON-decode each payload, classify into `header` / `type_a` / `type_b`, and return a `dict[uuid, {"header": ..., "type_a": [...], "type_b": [...]}]`.

**2. `_extract_sources` rewrite**

New return shape per source:

```python
{"source_id": "1", "url": str, "title": str, "snippet": str, "publisher": str, "favicon": str}
```

Build a source list by walking `ul.bTFeG > li.CyMdWb` in document order and, for each, looking up `data-src-id` against all Type-A payloads seen on the page (any UUID may carry the same source). Fill `title` / `snippet` / `favicon` from the payload; fall back to the tray's `span.Z1JFYc` for `publisher` if the payload's `[publisher]` slot is missing.

**IMPORTANT: preserve the rank order of the sources as they appear in the inline tray.** Do not reorder by `source_id`, by payload arrival order, or by publisher. The tray order is Google's curated ranking and is meaningful to downstream consumers.

`text` field is removed in favor of explicit `publisher` / `title` — downstream consumers (e.g., SearchAudits) need to be updated. Flag in CHANGELOG.

**3. `_extract_body` text cleanup + citations**

Before any `get_text()` call, `decompose()` every `button.rBl3me` from the section/paragraph element so the trailing `"Publisher +N"` text stops leaking. This is a ~3-line fix at the top of `_extract_body`.

Per section (and at the top level for lede-attached buttons), attach a `citations` array. For each button found within the element scope:

```python
{"publisher": "Yahoo Finance",     # None for unattributed
 "additional_count": 1,            # 0 if no IjM6od span
 "source_ids": ["2", "1"]}         # in payload order; may be shorter than total if some lack data-src-id
```

Unattributed buttons with no payload data → skip entirely. Unattributed buttons with payload data → emit with `publisher: None`.

### Resulting shape

```python
{
  "type": "ai_overview",
  "sub_type": "sectioned" | "flat",
  "title": <first section heading or None>,
  "text": <lede>,
  "url": None,
  "cite": None,
  "details": {
    "type": "ai_overview",
    "sections": [
      {"heading": str, "text": str,
       "hyperlinks": [...],  # existing
       "citations": [{"publisher": str | None, "additional_count": int, "source_ids": [str, ...]}, ...]},
      ...
    ],
    "citations": [...],   # lede-level (optional, only if any)
    "sources": [
      {"source_id": "1", "url": str, "title": str, "snippet": str, "publisher": str, "favicon": str},
      ...
    ],
  }
}
```

### Repro / inspection

- `uv run python scripts/show_serp.py "best credit cards" --data-dir data/demo-ws-v0.6.10a0 --raw` — renders the buttons + sources tray together; useful for visual verification.
- HTML-comment example (most common path, from `best credit cards`):
  ```
  <!--TgQPHd|[["<uuid>",[<title>,<snippet>,<favicon>,<domain>,[<publisher>],<full_url>,null,null,"<data-src-id>",...]]]-->
  ```
- `Sv6Kpe` variant (from `translate thank you to korean` in `data/demo-ws-v0.6.8a1`): identical inner structure, no `|` between token and JSON.
- `jsdata` fallback (from `how does photosynthesis work` in `data/demo-ws-v0.6.8a2`):
  ```
  (j.lDPB=j.lDPB||[]).push([["gTO3eb_67","[[\"<uuid>\",[\"<title>\",...]]"]]);
  ```

### Build order

1. Write the payload-extraction module + unit tests against fixtures in `tests/fixtures/`.
2. Rewrite `_extract_sources` and update existing snapshots in lockstep. Verify rank order is preserved across the 26 SERPs touched by plan 021.
3. Add the `button.rBl3me` decompose + citation extraction in `_extract_body`. Regenerate snapshots.
4. Update CHANGELOG with the schema change (note `sources[*].text` → `sources[*].publisher` plus new fields).
5. Regression check: `uv run python scripts/survey_ai_overviews.py` across all 7 demo datasets; spot-check 3 SERPs visually with `show_serp.py`.

### Notes

- Comment parsing must run on raw HTML, not the bs4 tree.
- Two registrar tokens (`TgQPHd`, `Sv6Kpe`) — the `Sv6Kpe` variant has no `|` separator before its JSON.
- 26 SERP snapshots will need regeneration (same set plan 021 touched).
- Downstream consumers (SearchAudits) will see breaking changes on `sources[*]`. Mention in CHANGELOG under the next version's "Changed" section.
