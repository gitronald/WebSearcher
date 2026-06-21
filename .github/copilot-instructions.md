# WebSearcher Copilot Agent Instructions

Welcome to the WebSearcher repository. This document outlines how a cloud agent can work most efficiently when interacting with this codebase.

## Overview

WebSearcher is a Python package for conducting algorithm audits of web search. It uses `selenium` for geolocating and executing searches, and `selectolax` for parsing the resulting SERPs (Search Engine Results Pages) into categorized components.

## Technical Stack & Commands

- **Language:** Python >= 3.12 (CI matrix: 3.12, 3.13, 3.14)
- **Package Manager:** `uv` (use `uv run` for executing scripts/tests, `uv add` for dependencies). Sync dev deps with `uv sync --all-groups`.
- **Testing:** `pytest` with `syrupy` for snapshot testing (`uv run pytest`)
- **Linting & Formatting:** `ruff` (`uv run ruff check .` and `uv run ruff format --check .`)
- **Type Checking:** `pyrefly` (`uv run pyrefly check`)
- **Pre-commit:** Configuration exists in `.pre-commit-config.yaml`
- **Parsing Backend:** `selectolax` (C-backed CSS engine, replaced BeautifulSoup/lxml)

The CI gate (`.github/workflows/test.yml`) runs, in order: `ruff check`, `ruff format --check`, `pyrefly check`, then `pytest --cov`. Match it locally before reporting progress.

## Architectural Guidelines

### The Parser Pipeline (`selectolax`)

WebSearcher relies heavily on `selectolax` for high-performance DOM parsing. The selectolax conventions and bs4-compatibility helpers live in `WebSearcher/_slx.py` — review it before writing or modifying any parsing code.

Key `selectolax` differences from BeautifulSoup (bs4):
1. **Node selection:** `node.css("div.cls")` matches the node itself if it has the class. Use `_slx.subtree_first` / `_slx.subtree_css` for descendants-only semantics.
2. **Document traversal:** `node.traverse()` walks the *entire* document past the subtree. Never use it on a component node. Use `_slx.walk_descendants(node)` instead.
3. **Attributes:** `.attributes` allocates a new dict; prefer `.attrs` (e.g., `el.attrs.get("class")`). Use `el.id` instead of `el.attrs.get("id")`.
4. **Class tokens:** Classes are single strings, not lists. Use `_slx.class_tokens(node)` for list-like checking.
5. **Text extraction:** Native `node.text(strip=True)` doesn't strip empty fragments. Use `_slx.get_text(node, " ", strip=True)` for bs4-faithful behavior.
6. **Identity:** Use `node.mem_id` instead of `id(node)` to uniquely identify DOM elements.

The `.claude/skills/convert-bs4-to-selectolax/` skill captures the full migration playbook (note: `.claude/` is gitignored and may not be present in a fresh checkout).

### Parser package layout

The parse pipeline lives under `WebSearcher/parsers/`:
- `parse_serp.py` — the orchestrator, exposed as `WebSearcher.parse_serp` (`from WebSearcher.parsers.parse_serp import parse_serp`). It is intentionally *not* re-exported from `parsers/__init__.py` to avoid a circular import.
- `component.py`, `component_list.py`, `component_types.py` — the leaf machinery (`Component`, classification types, `header_text_to_type`).
- `components/` — one module per component type, plus the `PARSERS` dispatch registry in `components/__init__.py`.

### Adding or Modifying Parsers

1. Add/modify the classifier in `WebSearcher/classifiers/{main,footer}.py` (and `WebSearcher/parsers/component_types.py` for header-text → type mapping).
2. Add/modify the parser module in `WebSearcher/parsers/components/{cmpt_name}.py`.
3. Register the parser in the `PARSERS` dict in `WebSearcher/parsers/components/__init__.py` (`"type_name": parse_<type>`).
4. Follow the parser contract documented at the top of `components/__init__.py`: a module-level function `def parse_<type>(elem: Node) -> list[dict]` (no parser classes), where `elem` is a selectolax `LexborNode`. Return a `list[dict]`, each carrying at least `type`. `parse_unknown` is the catch-all for `unknown` components.
5. Avoid generating full document strings via `get_text` when a simple `css_first` substring check suffices. Let C do the work via CSS selectors.

### Testing and Snapshots

The test suite uses snapshots of parsed SERPs based on a compressed fixture corpus at `tests/fixtures/serps.json.bz2`.
- Run tests: `uv run pytest -q`
- Update snapshots after intentional changes: `uv run pytest --snapshot-update`
- For changes to the parser, it is CRITICAL that snapshot updates are carefully verified to ensure no unintended regressions occur on existing components.
- Coverage and corpus-integrity guards live in `tests/test_parser_coverage.py` and `tests/test_corpus_integrity.py`.

## Plans

Active and historical work is tracked under `.planners/` (the `planners` package owns the lifecycle). Consult `.planners/README.md` for the plan index when investigating prior decisions.

## General Best Practices

- Make surgical changes when addressing issues or features.
- Provide a summary checklist of progress via `report_progress`.
- Only use standard environment tools (`bash`, `uv`, `git`, `grep`, `view`, etc.).
- Always prefer ecosystem tools (like `uv` or `ruff`) for dependency management and linting/formatting.
- Ensure new or updated code passes `ruff check`, `ruff format`, and `pyrefly check`.
