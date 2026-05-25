---
status: active
branch: feature/ai-overview-sge-and-parser-coverage-fixes
created: 2026-05-24T17:13:20-07:00
completed:
pr:
---

# AI Overview legacy-SGE recovery and parser coverage fixes

## Plan

A full-corpus reparse audit (run against WS 0.8.1 / 0.8.2 on a large
historical crawl) surfaced one AI-Overview extraction gap on 2024-era markup
plus eight component-parser coverage issues. This plan fixes them in one
branch, phased, starting with the AI Overview legacy-SGE gap. Each phase
stands alone (own fixtures + verification) so phases can land as separate
commits.

The audit measured counts/percentages against a private downstream corpus;
those figures are reproduced here only to rank impact. All verification in
this plan runs against fixtures committed to **this** repo (see Phase 0) — no
external data path is referenced.

### Phase 0 — Representative fixtures (do first)

The repo already ships compressed JSONL SERP fixtures
(`tests/fixtures/serps-v0.6.7.json.bz2`, `…-v0.6.8.json.bz2`,
`…-v0.7.2-*.json.bz2`). Add small, issue-targeted fixtures in the same shape
(JSONL of `{qry, html, serp_id, ...}`, bz2-compressed) so every fix below has
a committed, reproducible repro:

- `tests/fixtures/serps-sge-2024.json.bz2` — 2024-era SERPs whose `ai_overview`
  component carries recoverable synthesized text + sources (the
  content-bearing ~1/3), plus a couple of genuine "Can't generate an AI
  overview right now" failures (must stay empty).
- `tests/fixtures/serps-parser-coverage.json.bz2` — a handful of SERPs each for
  `recipes`, `knowledge` (featured_results / dictionary / panel_rhs),
  `twitter_cards`, `shopping_ads`, and the `general` null-extraction case.

Keep these tiny (a few SERPs per issue) — they are regression anchors, not a
corpus. Source HTML from representative SERPs already captured for this work;
strip to the minimal `{qry, html, serp_id}` record shape used by the existing
fixtures. Example queries that exercise each issue: `cherrypie` /
`ocean spray cranberry banana bread` (recipes), `define:escheat` /
`what is the need` (dictionary), `pokemongo` / `ary news` (twitter_cards),
`my work is done why wait` (content-bearing AI overview).

Add a short loader/repro snippet pattern (used throughout below):

```bash
uv run python - <<'PY'
import bz2, json
import WebSearcher as ws
from WebSearcher.parsers import parse_serp
path = "tests/fixtures/serps-sge-2024.json.bz2"
with bz2.open(path, "rt") as f:
    serps = [json.loads(l) for l in f]
serp = next(s for s in serps if s["qry"] == "my work is done why wait")
parsed = parse_serp(serp["html"])
aio = [r for r in parsed["results"] if r["type"] == "ai_overview"]
print(json.dumps(aio, indent=2)[:2000])
PY
```

### Phase 1 — AI Overview: legacy SGE (2024) markup support

**Problem.** On 2024-era crawls, `ai_overview` is *detected* correctly (the
`div.Fzsovc` marker is still present) but extraction returns empty: `text=null`,
`details=null`, `has_details=false`. ~1/3 of detected overviews actually
generated content (synthesized answer + source links) and are being silently
dropped; the other ~2/3 are genuine "Can't generate an AI overview right now"
panels that *should* stay empty.

**Root cause.** `WebSearcher/component_parsers/ai_overview.py` is hard-wired to
the *current* AI Overview DOM:
- body container `div.mZJni` (`ai_overview.py:36`)
- paragraphs `Y3BBE`, headings `otQkpb`, lists `KsbFXc` / `IaGLZe`
  (`_BODY_PARA_CLASS` / `_BODY_HEADING_CLASS` / `_LIST_CLASSES`, lines 55-57)
- sources tray `ul.bTFeG` > `li.CyMdWb` (`_extract_sources`, lines 295-336)
- citation buttons `button.rBl3me`

None of these classes exist in the 2024 SGE (Search Generative Experience)
markup, so `content` is `None`, `_extract_body` short-circuits, and
`_extract_sources` finds no tray.

**Approach.**
1. Discovery: identify the 2024-SGE class names for body container, paragraph,
   heading, list, source tray, and source link. Use the existing inspection
   scripts against the new fixture:
   - `scripts/inspect_ai_overview_structure.py` — structural skeleton
   - `scripts/dump_ai_overview_html.py` — dump the real overview HTML
   - `scripts/survey_ai_overviews.py` — cross-SERP structural summary

   **Stale helper to fix in this phase:** `dump_ai_overview_html.py`'s
   `is_real_ai_overview` still checks `ClassifyMain.ai_overview(...) != "knowledge"`,
   which predates plan 021's promotion of `ai_overview` to a top-level type — the
   classifier now returns `"ai_overview"`/`"unknown"`, so the helper currently
   matches nothing. Update it (and check `survey_ai_overviews.py` for the same
   stale check) before relying on these scripts.
2. Generalize the selectors to accept current-or-legacy class sets rather than
   single literals — e.g. make `content = cmpt.find("div", {"class": "mZJni"})`
   fall back to the legacy body class; widen `_BODY_PARA_CLASS` /
   `_BODY_HEADING_CLASS` / `_LIST_CLASSES` and the `ul.bTFeG` tray lookup to
   tuples of accepted classes. Keep the JSON-payload citation path
   (`_ai_overview_payloads`) as current-only; legacy SGE predates those
   payloads, so legacy sources come from the rendered tray anchors directly.
3. Preserve the empty-on-failure contract: "Can't generate an AI overview
   right now" panels must still yield `text=None`, `details=None`.

**Files.** `WebSearcher/component_parsers/ai_overview.py` (selector
generalization). Possibly `_ai_overview_payloads.py` only if a legacy payload
form is found (likely not).

**Verify.** Repro snippet from Phase 0 — the content-bearing fixture SERP must
return non-null `text` and a `details.sources` list with real publisher URLs;
the "can't generate" fixtures must stay empty. Run `/compare-parsed` to confirm
no regression on current-DOM AI Overviews in the demo dataset.

### Phase 2 — `recipes`: add a structured parser (currently unparsed)

**Problem.** Every `recipes` row carries unstructured `text` as a
`<|>`-separated dump, no `title` / `url`
(e.g. `"Recipes<|>Beer Bread<|>Food.com<|>5.0<|>(1.1K)<|>1 hr 3 min<|>…"`).

**Root cause.** `recipes` is a registered component type
(`component_types.py:304`, `name="recipes"`) but has **no entry in `PARSERS`**
(`component_parsers/__init__.py`). Unmapped main-section types dispatch to
`parse_not_implemented` / `parse_unknown` (`components.py:70-78`), whose
`get_text("<|>", strip=True)` produces exactly the observed dump.

**Approach.** Write `WebSearcher/component_parsers/recipes.py::parse_recipes`
and register it in `PARSERS`. Split each recipe card into `title`, `url`, and a
`details` block — reuse an existing controlled-vocabulary `type` (likely
`ratings` for rating/n_reviews and the cook-time/source fields, per the schema
conventions in CLAUDE.md), rather than inventing a new label. Confirm the recipe
card selectors from the fixture HTML during implementation.

**Files.** New `component_parsers/recipes.py`; register in
`component_parsers/__init__.py` `PARSERS`. Verify the type's section assignment
in `component_types.py`.

**Verify.** Parse the `cherrypie` fixture SERP; assert each recipe row has a
`title` + `url` and no `<|>` in `text`.

### Phase 3 — `knowledge`: empty featured_results / dictionary / panel_rhs

**Problem (three related gaps).**
- `knowledge.featured_results` — ~99% entirely empty (no url/title/text). Hits
  song-lyric and featured-result panels.
- `knowledge.dictionary` — 100% empty; Google dictionary panels extract nothing.
- `knowledge.panel_rhs` — ~39% empty placeholder rows mixed with correctly
  extracted Wikipedia-style entity panels.

**Root cause.** The sub_type classification fires
(`knowledge.py`: `featured_results` at line 47, `dictionary` at 82-85) but the
body-extraction path returns nothing for these variants. `panel_rhs` is a
separate parser (`knowledge_rhs.py::parse_knowledge_rhs`) that emits placeholder
rows for layouts it doesn't extract.

**Approach.** Per sub_type, inspect the fixture HTML and add targeted
extraction:
- `featured_results` / lyrics: pull the answer/lyric `text` and any source
  link into `title` / `url`.
- `dictionary`: extract headword, phonetic, part-of-speech, and definitions —
  reuse `details.type=text` (`{items: [...]}`) for the definition list unless a
  richer existing label fits.
- `panel_rhs`: distinguish genuine empty placeholders from extractable entity
  panels; for the extractable ones add title/url/text; for true placeholders
  set `details=None` and drop hollow rows per the schema-discipline rule.

**Files.** `component_parsers/knowledge.py`, `component_parsers/knowledge_rhs.py`.

**Verify.** Parse the dictionary (`define:escheat`), featured-results, and
panel_rhs fixtures; assert non-empty extraction on content-bearing SERPs and
`details=None` (no hollow dict) on genuine placeholders.

### Phase 4 — `twitter_cards.card`: legacy layout missing title/text

**Problem.** ~86% of `twitter_cards.card` rows have a URL but no `title` and no
tweet `text`. (`twitter_cards.header` extracts cleanly.) Note this contradicts
the standing TODO claim that `twitter_cards`/`twitter_result` "never fire on
modern SERPs" — they *do* fire on the 2024-era crawl; that TODO item is a
layout-era distinction to reconcile, not a contradiction.

**Root cause.** `parse_twitter_card` (`twitter_cards.py:43-58`) reads the
account title from `g-link` and the tweet text from `div.Brgz0 > div.xcQxib`
(cite from `div.rmxqbe`). These class names are stale for the 2024 card layout,
so `title`/`text` come back null while the deep-link URL (from a different path)
still resolves.

**Approach.** Add the 2024 card selectors as fallbacks for title, text, and
cite (mirroring the current-or-legacy header handling already in
`parse_twitter_header`, lines 22-40). Identify the legacy classes from the
`pokemongo` / `ary news` fixtures.

**Files.** `component_parsers/twitter_cards.py`.

**Verify.** Parse the twitter fixtures; assert `card` rows carry `title` +
`text` + `url`.

### Phase 5 — `general` and `shopping_ads` extraction errors

**`general` errors (~1.7% of general rows).** `sub_type=null` with `cite` /
`text` / `url` all null. Low rate but real. Inspect the
`general`-error fixture SERPs and trace which layout variant in
`parse_subtype_details` (general.py elif chain) the rows fall through; add the
missing branch or a fallback. Watch the shared dependency noted in CLAUDE.md
(the general subtype elif chain has dormant branches).

**`shopping_ads` errors (~12% of shopping_ads).** `_parse_pla_unit`
(`shopping_ads.py:22-28`) only populates `url`/`title` when it finds
`a.clickable-card` with an `aria-label`; cards using a different anchor/label
yield empty rows. Add a fallback for the alternate PLA card markup.

**Files.** `component_parsers/general.py`, `component_parsers/shopping_ads.py`.

**Verify.** Parse the respective fixtures; assert previously-empty rows now
carry url/title.

### Phase 6 — `unknown` residual (survey, lowest priority)

**Problem.** ~7.7k residual `unknown` rows, scattered mid-page across diverse
queries (94% of affected SERPs have just one), suggesting many small
unrecognized layouts rather than one missing class. Down sharply from earlier
versions.

**Approach.** Survey the `unknown` fixtures to bucket recurring layouts; file
follow-up classifier/parser additions for any cluster that's clearly one
component type. Do **not** chase long-tail singletons in this plan — capture
findings and spin out separate TODO items for anything substantial.

**Files.** Investigation only; changes (if any) in `classifiers/main.py` +
the relevant parser.

### Cross-cutting notes

- **Shared parsers (per CLAUDE.md).** `top_stories.parse_top_stories` backs five
  component types; none are touched here, but run `/compare-parsed` after every
  phase to catch unintended ripples. Classifier order in `classifiers/main.py`
  matters — adding/reordering for Phase 6 must not absorb `available_on` /
  `knowledge_panel` matches.
- **Schema discipline (per CLAUDE.md + memory).** Reuse existing `details.type`
  labels (`text` / `hyperlinks` / `ratings` / `place` / `panel` / `video`);
  emit `details=None` rather than null-filled dicts.
- **Downstream compatibility.** A downstream consumer uses dict-style access on
  WS result objects; new fields are additive, but any change to the
  `ai_overview` `details` shape (Phase 1) should stay consistent with the
  current `{type, sections?, citations?, sources?}` contract.
- **Release docs.** On version bump, hand-update README "## Recent Changes" and
  promote the CHANGELOG `[Unreleased]` section (stanza touches neither).

### Out of scope

- Reparsing or promoting any downstream corpus (a consumer-side decision).
- Micro-benchmarking the parse pipeline (covered by plan 023).
- Long-tail `unknown` singletons (Phase 6 buckets only).

### Suggested commit order

Phase 0 (fixtures) → Phase 1 (AI Overview) → Phase 2 (recipes) →
Phase 3 (knowledge) → Phase 4 (twitter_cards) → Phase 5 (general + shopping_ads)
→ Phase 6 (unknown survey). One commit per phase.

## Log

### Phase 0 — fixtures built

Selected verified SERPs by parsing candidates with current WS (0.8.3a0) and
confirming each exhibits its issue, rather than by query name (the downstream
note's example queries were drawn from the full crawl, not the seeded sample).
Records stripped to the existing fixture key shape; internal `crawl_id` blanked.

**`tests/fixtures/serps-sge-2024.json.bz2`** (583 KB, 5 SERPs) — every SERP
produces an `ai_overview` row that current code leaves `text=null` (the gap):
- content-bearing (real `div.rPeykc` answer text): `my work is done why wait`
  (flagship — sources with `#:~:text=` fragments + an "Explanation" section),
  `metropolitan los angeles area`, `barclays job cuts`
- genuine empties (`rPeykc_n=0`): `tesla manifesto`, `honeywell c level
  management figures`

**`tests/fixtures/serps-parser-coverage.json.bz2`** (3.2 MB, 15 SERPs) — 2 per
issue plus one non-empty `panel_rhs` for regression coverage:
- recipes: `birthday cake with candles`, `biscuit and gravy recipe`
- knowledge/featured_results (empty): `mater (cars)`, `pitbull i believe that we will win`
- knowledge/dictionary (empty): `cistern`, `define judgement`
- knowledge/panel_rhs (empty): `red skin peanuts`, `file folder`
- knowledge/panel_rhs (non-empty, regression anchor): `prouve`
- twitter_cards/card (no title): `movement`, `oscar the grouch`
- general error (null sub_type+url+text+cite): `men's old school wears`, `kaka boots`
- shopping_ads error (no url/title): `drawing tablet`, `kelly kettle`

**Discovery for Phase 1 (2024-SGE selectors).** The "Can't generate an AI
overview right now" string is a hidden fallback present on *every* AI-overview
page (including content-bearing ones), so it is **not** a content-vs-failure
discriminator — presence of `div.rPeykc` body text is. Located the 2024-SGE
markup in the content fixtures (none of which the current parser targets):
- body answer paragraphs: `div.rPeykc` (nested under `div.WaaZC` /
  `div.LT6XE` / `div.UxeQfc`) — vs current `div.mZJni` / `Y3BBE`
- section heading label: `"Explanation"` heading observed in the flagship SERP
- source links: `a.KEVENd` anchors inside `li.LLtSOc` cards, carrying
  `#:~:text=` deep-link fragments — vs current `ul.bTFeG` / `li.CyMdWb`

The current `div.Fzsovc` marker (detection) holds only the "AI Overview" label
(or "Searching" on mid-load captures), not the answer body.

**Stale helper found (fix in Phase 1, not yet done).**
`scripts/dump_ai_overview_html.py::is_real_ai_overview` gates on
`ClassifyMain.ai_overview(...) != "knowledge"`, which predates plan 021's
promotion of `ai_overview` to a top-level type. On current code the classifier
returns `"ai_overview"`/`"unknown"`, so the helper matches nothing (its scan
over all 15,003 AI-overview SERPs returned zero). `survey_ai_overviews.py`
likely shares the same stale gate. Both need updating before they're used in
Phase 1 discovery.

### Branch

Created `feature/ai-overview-sge-and-parser-coverage-fixes` and moved the
Phase 0 commits (plan + fixtures, originally committed on `dev` while the plan
was a draft) onto it; `dev` restored to `origin/dev`. Status flipped
`draft -> active`. The two commits were local-only, so no shared history was
rewritten.

### Phase 1 — AI Overview legacy SGE: done

Added a legacy branch to `parse_ai_overview`: when the current-DOM body
container `div.mZJni` is absent, fall back to `_extract_body_legacy` +
`_extract_sources_legacy`. The current path is left byte-identical (only
restructured into an `if/else`), and the legacy branch is unreachable on any
current-DOM SERP, so there is no regression risk.

- **Body** — walk `div.rPeykc` blocks + plain content `ul`/`ol` lists in
  document order; a `rPeykc` wrapping a `[role=heading]` (other than the
  `Fzsovc` "AI Overview" label) opens a section. Legacy captures predate the
  JSON citation payloads, so `lede_citations` is always empty here.
- **Sources** — read straight from `li.LLtSOc` tray cards: `a.KEVENd` href +
  `aria-label` title (fallback `div.mNme1d`), snippet `span.gxZfx`. `source_id`
  and `favicon` (a large base64 data URI) left `None`; `publisher` `""`.
- **Failures** — "Can't generate" panels have none of these markers, so the
  branch yields empty `text`/`details` (verified the "Can't generate" string is
  a hidden fallback on *every* AI-overview page, including content-bearing ones,
  so it is not used as a signal).

Fixed the stale helper `scripts/dump_ai_overview_html.py` (`!= "knowledge"` ->
`!= "ai_overview"`); `survey_ai_overviews.py` already used the correct gate.

**Verification.** New `tests/test_ai_overview_legacy_sge.py` (5 cases) asserts
content recovery (text + sources w/ url+title) and empty-on-failure. Full suite
green (267 passed, 66 snapshots). Confirmed no current-DOM regression: all 108
`mZJni` AI overviews in demo/fixtures still extract text+sources+citations, and
0 corpus SERPs reach the legacy branch (every `ai_overview` row co-occurs with
`mZJni`).
