# WebSearcher

Parser library for Google search result pages. Each SERP is decomposed into a typed list of `results` (e.g. `general`, `top_stories`, `perspectives`, `local_results`, `available_on`, `videos`, `searches_related`, ...) by an `Extractor` + `ClassifyMain`/`ClassifyFooter` pipeline, then per-component parsers populate `title`, `url`, `text`, `cite`, `details`, etc.

## Running code

All Python execution goes through `uv` (the project's `.python-version` is 3.14):

```bash
uv run python scripts/...
uv run pytest
```

Do not use `poetry`, `python`, or `python3` directly. Some skill files still reference `poetry` from before the migration — treat those as stale.

## Inspection scripts

Use these when diagnosing parser issues or auditing a demo dataset:

| Script | When |
|---|---|
| `scripts/show_parsed.py "{query}" --data-dir {dir}` | See the parsed-results table for a SERP (rank, type, sub_type, title, url, details summary). Re-parses fresh on every call — always reflects current code. |
| `scripts/show_serp.py "{query}" --data-dir {dir}` | Serve the saved HTML on localhost:8765 with Google's overlays/scroll-locks stripped. `--raw` keeps the original. |
| `scripts/demo_screenshot.py --data-dir {dir}` | Render a screenshot of the SERP with component-type colored borders. |
| `scripts/show_serp.py --list --data-dir {dir}` | List the queries in a dataset. |

Default `--data-dir` resolves to `data/demo-ws-v{ws.__version__}/`. Pass an explicit path for older fixtures or `/tmp` extracts.

## Demo data layout

```
data/demo-ws-v{version}/
  serps.json     # JSONL: {qry, html, serp_id, ...}
  parsed.json    # JSONL: {results: [...], features: {...}, ...} — pre-parsed output
  searches.json  # JSONL: {qry, serp_id, timestamp, ...} — search metadata
tests/fixtures/
  serps-v0.6.7.json.bz2   # older bz2-compressed JSONL fixtures
  serps-v0.6.8.json.bz2   # — useful for regressions; the "northern lights" SERP used in plan 018/019 lives here
```

## Skills (`.claude/skills/`)

| Skill | Use case |
|---|---|
| `/parser-update` | 7-phase parser diagnose-and-fix workflow on demo data. Now references the inspection scripts above. |
| `/compare-parsed` | Compare parsed output before/after uncommitted changes — regression check. |
| `/compare-selectors` | Diff selectors between current and committed versions of a parser file. |
| `/reparse` | Re-parse fixtures with current code and diff against pre-parsed output. |

## Plans and TODO

- `docs/plans/{NNN}-{slug}.md` — design specs with `status: draft|active|done|abandoned` frontmatter
- `TODO.md` — gitignored, flat list of open/closed items, each pointing to a plan or marked `(no plan)`

Conventions per global rules in `~/.claude/rules/plan-files.md` and `~/.claude/rules/todo-files.md`.

## Schema conventions

A `details` block on a parsed result uses a controlled vocabulary of `type` values. Try to reuse existing labels rather than invent new ones:

- `text` — `{items: [str, ...]}` (people_also_ask, searches_related)
- `hyperlinks` — `{items: [{url, text, ...}]}` (available_on, top_image_carousel, knowledge_rhs, footer image cards, general submenu)
- `ratings` — rating data, see general's modern rating widget and shopping_ads
- `place` — local_results: rating, n_reviews, price, category, address, phone, hours, review_snippet, website, directions
- `panel`, `video` — used by knowledge / general video subtypes

When a `details` block would have only null fields, set `details=None` instead of emitting a hollow dict.

## Notable parser dependencies

- `top_stories.parse_top_stories` is shared by `top_stories`, `perspectives`, `local_news`, `recent_posts`, and `latest_from`. One selector change ripples to all five. Verify with `/compare-parsed` after edits.
- `parse_subtype_details` in `general.py` has its own elif chain for layout variants (subresult, submenu, submenu_rating, submenu_mini, submenu_scholarly, submenu_product). Some branches are dormant on modern SERPs; modern rating widget reads from `Y0A0hc`/`z3HNkc` aria-labels.
- `classifiers/main.py` runs an ordered chain of classifiers; order matters when components match multiple. `available_on` was recently moved ahead of `knowledge_panel` because the streaming-providers widget was being absorbed.
