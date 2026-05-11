---
status: active
branch: feature/promote-ai-overview-component
created: 2026-05-10T18:46:52-07:00
completed:
pr:
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
4. Keep the dict-access compatibility surface that `~/repos/SearchAudits` relies on (see `reference_searchaudits` memory).

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

7. **Downstream-compat note.** Verify `~/repos/SearchAudits` still loads cleanly — its dict-style access on WS objects means any consumer reading `r["sub_type"] == "ai_overview"` will need to switch to `r["type"] == "ai_overview"`. Add a heads-up in the Log and reach out before bumping the next WS minor.

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

