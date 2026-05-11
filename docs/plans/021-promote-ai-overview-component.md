---
status: draft
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
