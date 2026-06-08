# WebSearcher Copilot Agent Instructions

Welcome to the WebSearcher repository. This document outlines how a cloud agent can work most efficiently when interacting with this codebase.

## Overview

WebSearcher is a Python package for conducting algorithm audits of web search. It uses `selenium` for geolocating and executing searches, and `selectolax` for parsing the resulting SERPs (Search Engine Results Pages) into categorized components.

## Technical Stack & Commands

- **Language:** Python >= 3.12
- **Package Manager:** `uv` (use `uv run` for executing scripts/tests, `uv add` for dependencies)
- **Testing:** `pytest` with `syrupy` for snapshot testing (`uv run pytest tests/`)
- **Linting & Formatting:** `ruff` (`uv run ruff check` and `uv run ruff format`)
- **Pre-commit:** Configuration exists in `.pre-commit-config.yaml`
- **Parsing Backend:** `selectolax` (C-backed CSS engine, replaced BeautifulSoup/lxml)

## Architectural Guidelines

### The Parser Pipeline (`selectolax`)
WebSearcher relies heavily on `selectolax` for high-performance DOM parsing. Please review `docs/guides/selectolax-parsers.md` before writing or modifying any parsing code.

Key `selectolax` differences from BeautifulSoup (bs4):
1. **Node selection:** `node.css("div.cls")` matches the node itself if it has the class. Use `WebSearcher._slx.subtree_first` or `subtree_css` for descendants-only semantics.
2. **Document traversal:** `node.traverse()` walks the *entire* document past the subtree. Never use it on a component node. Use `_slx.walk_descendants(node)` instead.
3. **Attributes:** `.attributes` allocates a new dict; prefer `.attrs` (e.g., `el.attrs.get("class")`). Use `el.id` instead of `el.attrs.get("id")`.
4. **Class tokens:** Classes are single strings, not lists. Use `_slx.class_tokens(tag)` for list-like checking.
5. **Text extraction:** Native `node.text(strip=True)` doesn't strip empty fragments. Use `_slx.get_text(node, " ", strip=True)` for bs4-faithful behavior.
6. **Identity:** Use `node.mem_id` instead of `id(node)` to uniquely identify DOM elements.

### Adding or Modifying Parsers
1. Add/modify the classifier in `WebSearcher/classifiers/{main,footer,headers}.py`
2. Add/modify the parser in `WebSearcher/component_parsers/{cmpt_name}.py`
3. Add/register the new parser in `WebSearcher/component_parsers/__init__.py`
4. Avoid generating full document strings via `get_text` when a simple `css_first` substring check suffices. Let C do the work via CSS selectors.

### Testing and Snapshots
The test suite utilizes snapshots of parsed SERPs based on a compressed fixture corpus located at `tests/fixtures/serps.json.bz2`.
- Run tests: `uv run pytest tests/ -q`
- Update snapshots after intentional changes: `uv run pytest tests/ --snapshot-update`
- For changes to the parser, it is CRITICAL that snapshot updates are carefully verified to ensure no unintended regressions occur on existing components.

### Fixture Corpus Curating
When investigating test coverage or pruning the fixture corpus, use the tools provided in the `.claude/skills/corpus-curate/` directory (these are gitignored locally but available in the workspace). Check `docs/guides/fixture-corpus.md` for detailed rules on how records are scored and pruned.

## General Best Practices

- Make surgical changes when addressing issues or features.
- Provide a summary checklist of progress via `report_progress`.
- Only use standard environment tools (`bash`, `uv`, `git`, `grep`, `view`, etc.).
- Always prefer ecosystem tools (like `uv` or `ruff`) for dependency management and linting/formatting.
- Ensure new or updated code conforms to the project's formatting via `ruff`.
