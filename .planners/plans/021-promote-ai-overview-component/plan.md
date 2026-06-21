---
id: 21
slug: promote-ai-overview-component
status: done
branch: feature/promote-ai-overview-component
created: 2026-05-10T18:49:46-07:00
concluded: 2026-05-13T13:30:57-07:00
pr: https://github.com/gitronald/WebSearcher/pull/115
---

# Promote AI Overview to a top-level component with a structured, section-aware parser

## Plan

### Motivation

`ai_overview` is currently a `sub_type` under `knowledge`. The existing parser (`parse_knowledge_panel` in `WebSearcher/component_parsers/knowledge.py`) handles it by branching on `cmpt.find("div", {"class": "Fzsovc"})` (line 46) and then falling through the same generic-knowledge code path. The classifier (`ClassifyMain.ai_overview` in `WebSearcher/classifiers/main.py:185`) also routes AI overviews back to `"knowledge"`. The result is a single flat record with one `text` field and a long flat `details.urls` list, with no awareness of the multi-section structure that AI overviews actually have.

Across our stored datasets there are 76 AI-overview instances available for development and regression testing:

| Dataset                       | n  |
|-------------------------------|----|
| `data/demo-ws-v0.6.10a0/`     | 21 |
| `data/demo-ws-v0.6.8a2/`      | 14 |
| `data/demo-ws-v0.6.8a1/`      | 21 |
| `data/demo-ws-v0.6.8a0/`      | 13 |
| `data/demo-ws-v0.6.7a4/`      |  1 |
| `data/demo-ws-v0.6.7a2/`      |  3 |
| `data/demo-ws-v0.6.7a0/`      |  4 |

URL counts per overview range from 7 to 32+ in the most recent set, indicating these widgets have grown well past a single answer block. We need a structured representation.

### Goals

1. Make `ai_overview` a first-class `type` (no longer `sub_type` of `knowledge`).
2. Parse multi-section AI overviews into typed sections, each with its own heading, text, and hyperlinks — rather than a flat URL dump.
3. Cover all 76 examples in the demo datasets without regressing the knowledge parser for non-AI-overview panels.
4. Keep the dict-access compatibility surface that private downstream consumers rely on.

### Conceptual structure

Treat AI overview as "a larger knowledge with sections". The shape we want:

```
{
  "type": "ai_overview",
  "sub_type": <variant, e.g. "summary" | "comparison" | "list" | None>,
  "title": <top-level heading, e.g. "Best for Travel">,
  "text": <intro / lede summary text, if any>,
  "url": None,
  "cite": None,
  "details": {
    "type": "ai_overview",
    "sections": [
      {
        "heading": <section heading>,
        "text": <section body text>,
        "hyperlinks": [{"url": ..., "text": ...}, ...]
      },
      ...
    ],
    "sources": [{"url": ..., "text": ..., "domain": ...}, ...]
  }
}
```

Key shape decisions:

- Use `details.type = "ai_overview"` (new label) rather than recycling `panel`. The `details` vocabulary in `CLAUDE.md` already covers `text`, `hyperlinks`, `ratings`, `place`, `panel`, `video` — adding `ai_overview` is justified because none of those describe a multi-section synthesized answer.
- Each section's links use the existing `hyperlinks` shape (`{url, text}`), keeping vocabulary discipline (see `feedback_details_schema`).
- `sources` holds the deduplicated "Sources / References" tray at the bottom — distinct from per-section inline links because of how AI overviews are rendered and how downstream consumers (audit code) tend to want a flat citation list.
- Empty section text or empty link lists are omitted, not set to `None`-filled dicts (per `feedback_details_schema`).

### Implementation order

1. **Survey existing examples.** Write a one-off script under `scripts/` (or extend `scripts/show_parsed.py` invocations) that, for each demo dataset, dumps each `ai_overview` SERP's HTML node along with the current parsed record. Use this to inventory section-heading patterns, link layouts (inline anchors, "Sources" trays, footnotes), and any variants (e.g. comparison tables, bulleted lists). Save findings as a `## Log` entry on this plan.

2. **Promote the component type.**
   - In `WebSearcher/component_types.py`, add a new `ComponentType(name="ai_overview", label="AI Overview", sections=("main",), sub_types=(...), description="Google AI Overview synthesized answer")`. Determine sub_types after step 1.
   - Remove `"ai_overview"` from the `sub_types` tuple of the existing `knowledge` entry (line 185).

3. **Reroute classification.**
   - Change `ClassifyMain.ai_overview` in `WebSearcher/classifiers/main.py:185` to return `"ai_overview"` instead of `"knowledge"`.
   - Verify it still runs *before* `available_on` and `knowledge_panel` in the ordered chain (it does, line 71).

4. **Write the new parser.**
   - Create `WebSearcher/component_parsers/ai_overview.py` with `parse_ai_overview(cmpt, sub_rank=0) -> list[dict]`.
   - Detect sections (likely via `role="heading"` levels or `Fzsovc` substructure — confirm in step 1).
   - For each section, extract heading, body text, and inline hyperlinks (filtering `href="#"`, deduping, dropping `/search?` KG-nav links per the existing knowledge convention at line 127).
   - Extract the bottom "Sources" tray separately if present; otherwise leave `sources` out.
   - Register the parser in `WebSearcher/component_parsers/__init__.py` (alphabetical import + entry in the `PARSERS` dict).

5. **Remove the ai_overview branch from `parse_knowledge_panel`.** Drop the `elif cmpt.find("div", {"class": "Fzsovc"}):` branch at `knowledge.py:46`. Leave the rest of the knowledge parser intact.

6. **Regression check.**
   - Run `/compare-parsed` against `data/demo-ws-v0.6.10a0/` and `data/demo-ws-v0.6.8a1/` — every former `{type: knowledge, sub_type: ai_overview}` record should now be `{type: ai_overview, ...}` with a populated `details.sections`.
   - Spot-check 3–5 representative SERPs with `scripts/show_parsed.py "{query}" --data-dir data/demo-ws-v0.6.10a0/`.
   - Confirm non-AI-overview knowledge panels are byte-identical (use `/compare-parsed` filtered to `type=knowledge`).

7. **Downstream-compat note.** Any external consumer reading `r["sub_type"] == "ai_overview"` will need to switch to `r["type"] == "ai_overview"`. Add a heads-up in the Log; flag downstream owners before bumping the next WS minor.

8. **CHANGELOG.** Add an entry under the next version per `feedback_changelog_format` (Keep a Changelog `## [VERSION] - DATE` heading).

### Repro snippets

```bash
# Survey all AI overviews currently parsed across datasets
uv run python -c "
import json, pathlib
for p in sorted(pathlib.Path('data').glob('demo-ws-*/parsed.json')):
    with open(p) as f:
        for line in f:
            for r in json.loads(line).get('results', []):
                if r.get('sub_type') == 'ai_overview':
                    n = len((r.get('details') or {}).get('urls', []))
                    print(p.parent.name, r.get('cmpt_rank'), n)
"

# Inspect a specific SERP's AI overview (after picking a serp_id)
uv run python scripts/show_parsed.py "<query>" --data-dir data/demo-ws-v0.6.10a0/

# Open the SERP in a browser with overlays stripped
uv run python scripts/show_serp.py "<query>" --data-dir data/demo-ws-v0.6.10a0/
```

### Open questions

- Do we want to keep a `sub_type` axis on `ai_overview` (e.g. `summary` vs. `comparison`), or is the section-list shape enough? Decide after the step 1 survey.
- How aggressively should we dedupe `#:~:text=` fragment URLs against their base URLs in `sources`? Current `urls` lists include both forms; a downstream consumer may want each separately.
- Should `ai_overview` move up in the `ClassifyMain.classify` chain to run even earlier (e.g. before `top_stories`)? Only if step 1 finds an overlap; otherwise leave the order.

## Log

### 2026-05-10 — Step 1 survey

Wrote `scripts/survey_ai_overviews.py` and `scripts/inspect_ai_overview_structure.py` (+ `scripts/dump_ai_overview_html.py`) to inventory AI overview HTML.

**Counts (per-component, from raw HTML — not the same as parsed.json counts):**

| Dataset                  | Components flagged |
|--------------------------|---|
| `demo-ws-v0.6.10a0`      | 56 |
| `demo-ws-v0.6.8a1`       | 56 |
| `demo-ws-v0.6.8a0`       | 53 |
| (older sets)             | likely fewer |

**Key finding: the current classifier matches TWO different surfaces per SERP**

Every SERP with an AI overview has two components containing `div.Fzsovc`:
1. **The actual AI Overview** — compact widget, `h2 = None`, contains the synthesized answer + optional section subheadings (`role="heading" aria-level="3"`, class `otQkpb`) + a "Sources" tray.
2. **A "Related Links" expansion** — `h2 = "Related Links"`, contains "People also ask" plus extended sectioned content. This is currently classified as `knowledge` and produces a flat dump too, OR is absorbed by earlier classifiers in the chain. **Out of scope for this plan**; the new classifier must explicitly skip it (`h2.get_text(strip=True) != "Related Links"`).

That's why `parsed.json` reports ~21 `sub_type=ai_overview` records while the raw HTML survey finds 56 candidate components — many of the "Related Links" siblings reach `people_also_ask` or another classifier first.

**Layout structure (confirmed on 4 representative samples):**

The content body sits in `div.mZJni.Dn7Fzd`. Its inner sequence of children is:
- `div.Y3BBE` — lede / intro paragraph(s)
- `div.otQkpb` (`role=heading aria-level=3`) — section heading (when sectioned)
- `<ul class="KsbFXc U6u95">` — bullet list following the heading
- More `Y3BBE`/`otQkpb`/`ul` triples alternating

Sources tray: `ul.bTFeG > li.CyMdWb`, where each `li` is a card with one `<a href>` (the URL — often a `#:~:text=` fragment URL) and one `<span>` carrying the visible publisher name (e.g. `"CNN"`, `"NASA Space Place (.gov)"`).

Inline body anchors are rare (just 1 of 22 anchors in the "best credit cards" sample). The vast majority of anchors in the current flat `details.urls` come from the sources tray.

**Section-count distribution across 4 sampled SERPs:**

| Query | Lvl-3 section headings |
|---|---|
| `best credit cards` | 5 |
| `why is the sky blue?` | 0 |
| `best mattress forum` | 0 |
| `car insurance quotes` | 0 |

So both layouts (`sectioned` vs `flat`) need first-class support. About 1 in 4 has sections.

### Resolved open questions

- **`sub_type` axis:** keep simple — emit `sub_type="sectioned"` when there are aria-level-3 section headings, else `sub_type="flat"`. This is cheap and gives downstream consumers a coarse hint.
- **Fragment URL dedup:** keep all source URLs as-is (including `#:~:text=` fragments). Downstream code can strip the fragment if it wants the base URL; we shouldn't lose information here.
- **Classifier order:** leave at current position; the failure mode is that `Related Links` siblings get absorbed elsewhere, which we don't want to "fix" by reordering — we want to skip them in our matcher.

### Final shape decision

```python
{
  "type": "ai_overview",
  "sub_type": "sectioned" | "flat",
  "title": <first section heading or None>,
  "text": <lede paragraph(s), joined with " ">,
  "url": None,
  "cite": None,
  "details": {
    "type": "ai_overview",
    "sections": [
      {"heading": str, "text": str | None, "hyperlinks": [{"url", "text"}, ...]},
      ...
    ],  # omitted when flat
    "sources": [
      {"url": str, "text": str},  # text = publisher name
      ...
    ],
  }
}
```

### 2026-05-10 — Steps 2–7 implementation

Implementation committed in two pieces:

1. **Survey scripts + plan log** (commit `53341d`) — `scripts/survey_ai_overviews.py`, `inspect_ai_overview_structure.py`, `dump_ai_overview_html.py`.
2. **Core change + tests** (commit `827b2e`) —
   - `WebSearcher/component_types.py`: added `ai_overview` ComponentType, removed `ai_overview` from `knowledge.sub_types`.
   - `WebSearcher/classifiers/main.py`: `ClassifyMain.ai_overview` now returns `"ai_overview"` (not `"knowledge"`) and explicitly skips the `h2="Related Links"` sibling.
   - `WebSearcher/component_parsers/ai_overview.py`: new parser. Body extraction collects `div.Y3BBE` paragraphs, `div.otQkpb` section headings, and `ul.KsbFXc`/`ol.IaGLZe` lists in document order, splitting by heading. Sources come from `ul.bTFeG > li.CyMdWb`, with publisher names pulled from `span.Z1JFYc`.
   - `WebSearcher/component_parsers/__init__.py`: import + register `parse_ai_overview` in `PARSERS`.
   - `WebSearcher/component_parsers/knowledge.py`: removed the `Fzsovc` branch.
   - `tests/__snapshots__/`: regenerated for 26 SERPs that contained AI overviews.

**Regression check across 7 demo datasets:**

| Dataset | Old (`knowledge,ai_overview`) | New (`ai_overview`) | with `sections` | with `sources` | avg text len | errors |
|---|---|---|---|---|---|---|
| `demo-ws-v0.6.10a0` | 21 | 21 | 3 | 19 | 1184 | 0 |
| `demo-ws-v0.6.8a1`  | 21 | 21 | 2 | 21 | 1295 | 0 |
| `demo-ws-v0.6.8a0`  | 13 | 17 | 1 | 17 | 1725 | 0 |
| `demo-ws-v0.6.8a2`  | 14 | 14 | 1 | 14 | 1216 | 0 |
| `demo-ws-v0.6.7a4`  | 1  | 1  | 0 | 1  | 1102 | 0 |
| `demo-ws-v0.6.7a2`  | 3  | 3  | 0 | 3  | 1372 | 0 |
| `demo-ws-v0.6.7a0`  | 4  | 4  | 0 | 4  | 1628 | 0 |
| **total** | 77 | 81 | 7 | 79 | — | 0 |

`demo-ws-v0.6.8a0` picked up 4 additional overviews — previously absorbed by an earlier classifier in the chain when the AI overview lived alongside richer structure.

Full test suite passes (234 tests, 66 snapshots).

**Downstream impact to flag for external consumers:**

- Any consumer keyed on `r["type"] == "knowledge" and r["sub_type"] == "ai_overview"` must switch to `r["type"] == "ai_overview"`.
- `details["urls"]` (flat list of `{url, text}`) is replaced by `details["sources"]` (with publisher names) and optional `details["sections"]` (with their own `hyperlinks` lists).
- `details["type"]` is now `"ai_overview"` instead of `"panel"` for these records.

**Side effect: "Related Links" reclassification.**

The "Related Links" sibling that previously matched `Fzsovc` and was misclassified as `knowledge.ai_overview` now returns `"unknown"` from `ClassifyMain.ai_overview` and falls through to the next classifier. It typically lands on `people_also_ask` (its dominant content) and expands into multiple PAA rows. This is an improvement (it was previously a single flat dump), and the snapshot updates capture it — but downstream code should be aware that some former `ai_overview` rows are now `people_also_ask` rows. Out of scope for cleanup here; track separately if the new routing is problematic.

### Open follow-ups (out of scope)

- Inline-link extraction for sectioned overviews is sparse (1 link in the "best credit cards" sample). When more inline citations start surfacing, revisit.
- The `Related Links` blob, now routed to `people_also_ask`, has substructure (multi-section follow-up summaries) that's still being flattened. A dedicated `related_links_expansion` component could be added later if downstream consumers need it.
- **Section / lede citation buttons** (`button.rBl3me`). Each section (and the lede) ends with a small citation widget whose `aria-label` is `"Publisher (+N) - View related links"` (or generic `"View related links"` when unattributed). Inner spans: `span.iFMVXd` = publisher, `span.IjM6od` = `+N` count. Right now this leaks into our extracted section text (e.g., a section ends with `"Capital One +3"`). Future work: (a) skip these buttons during text extraction; (b) attach a `citation: {publisher, additional_count}` field per section and at the top level for the lede. 13 such buttons in the "best credit cards" sample.
- **Richer source cards.** `_extract_sources` currently emits `{url, text}` where `text` is the publisher only. Each `li.CyMdWb` source card actually carries `general`-result-grade data: `div.Nn35F` = title, `span.vhJ6Pe` = snippet (often with a date prefix like `"Mar 1, 2026 — ..."`), `span.Z1JFYc` = publisher, plus an `aria-label` on the anchor with `"Title. Opens in new tab."`. Future work: capture `title`, `snippet`, `publisher` (current `text`), and optionally a parsed `date` per source.
- **Side-panel vs inline-strip sources.** The same overview surfaces a `li.jydCyd` side-panel layout alongside `li.CyMdWb`. In the "best credit cards" sample `jydCyd` has 3 URLs, all of which are also in `CyMdWb` (14 total). Same inner structure as CyMdWb. Hypothesis: `jydCyd` is the "top results" subset shown in the expanded sidebar; needs cross-SERP confirmation. If always a subset, we can ignore. If sometimes carries unique URLs, merge into `details.sources` with a layout tag.
- **`show_serp.py` viewer changes** made during plan 021 to ease visual inspection: (a) `--raw` mode now serves the saved HTML with an injected strict Content-Security-Policy meta tag (`connect-src 'none'`, all third-party origins blocked) so inline scripts execute but can't phone home — fixes the mid-page tab-bar layout glitch we hit when serving over `http://127.0.0.1` and stops telemetry/ad-pixel beacons. (b) Default (non-`--raw`) mode unchanged: still strips scripts, removes overlays, breaks scroll-lock. If we want to drop the default's script-stripping now that CSP makes serving scripts safe, re-evaluate.

### 2026-05-13 — Follow-ups rolled into plan 022

The "Section / lede citation buttons" and "Richer source cards" items above are now tracked together in [plan 022](022-ai-overview-payload-citations.md). A subsequent audit found that both follow-ups feed off the same payload data Google embeds in HTML comments (`TgQPHd` / `Sv6Kpe` tokens) and a `jsdata.lDPB.push` fallback — every attributed `button.rBl3me` (143/143 across 81 demo SERPs) carries a structured record with `title`, `snippet`, `full_url`, `publisher`, and a `data-src-id` foreign key that joins back to the inline `bTFeG` sources tray. Plan 022 covers payload extraction, the `_extract_sources` rewrite, and `button.rBl3me` text-cleanup + per-section `citations`.

## Retrospective

- **The classifier-chain reroute was the riskiest part of the change, and it paid off.** Skipping the `h2="Related Links"` sibling in `ClassifyMain.ai_overview` not only stopped the misclassification but also revealed a previously buried `people_also_ask`-shaped blob — a regression-shaped improvement that we wouldn't have noticed if we'd kept the old routing.
- **Step 1's survey-before-code pass was worth doing.** Counting AI-overview occurrences across 7 demo datasets and inspecting the HTML structure before writing any parser code meant the `sectioned` vs. `flat` distinction, the `mZJni` content root, the `bTFeG`/`CyMdWb` sources tray, and the document-order walk were all baked in from the first draft — not retrofitted.
- **Snapshot churn was the dominant cost.** 26 SERPs regenerated. Worth budgeting up front next time we touch the parser for a high-visibility component — and worth knowing that plan 022 will regenerate the same 26 again.
- **The `details` schema decision (`sections` when present, `sources` always, omit `hyperlinks` when empty) followed [[feedback_details_schema]] cleanly.** No hollow null-filled blocks survived in the final output.
- **Out-of-scope discoveries got formal homes.** The `button.rBl3me` citation widgets and the richer source-card payload were both found *during* this work but consciously deferred to plan 022 — rather than scope-creeping 021. The pointer note at the end of the Log section makes the handoff explicit.
- **`show_serp.py --raw` plus an injected offline CSP turned out to be the cleanest debugging primitive.** Stripping scripts (the old default) hides too much; serving raw HTML over `http://127.0.0.1` lets layout settle naturally while CSP blocks telemetry/ad-pixel beacons. Worth reaching for first on future viewer changes.

