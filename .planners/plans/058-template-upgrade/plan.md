---
id: 58
slug: template-upgrade
status: draft
branch: feature/template-upgrade
created: 2026-10-14T18:49:31-07:00
concluded:
pr:
---

# Upgrade to proj-template 0.11.2

## Plan

Sync WebSearcher to the proj-template 0.11.2 standard with the template's `install-template`
upgrade process. WebSearcher has no `[tool.proj-template]` stamp, so every template file was
diffed against `template/` at the `v0.11.2` tag.

**Classification: package.** It has `[build-system]`, a `project.scripts` entry, and ships
to PyPI.

### Sync decisions per matrix row

| Template path | Decision |
|---|---|
| `[tool.ruff*]` | merge: add `extend-exclude = ["*.md"]`; keep the repo's `py312` target, `line-length = 100`, the `E501` ignore, and isort `known-first-party` |
| `[tool.pyrefly*]` | **replace with strict** (decision below): `preset = "strict"`, `project-includes = ["."]`, template `project-excludes` plus repo-local dirs, `tests/**` sub-config relaxing `implicit-any`; keep `python-version = "3.12"` and the `patchright` `ignore-missing-imports` |
| dev group | merge: `pyrefly>=1.0.0`, `ruff>=0.16,<0.17` (same minor as the hook rev); keep the repo's extra dev deps |
| pytest / coverage | merge: `testpaths = ["tests"]`, bare `--cov` in `addopts` (`run.source` names the package), `branch = true`, `exclude_lines`, `fail_under` set to the current total; keep the repo's `omit` and `show_missing` |
| `[build-system]`, sdist, urls, scripts | merge: root-anchor sdist `only-include` and add `/README.md`, `/LICENSE`; `https` repository URL; keep `homepage` and `ws-demo` |
| `[tool.proj-template]` | stamp `0.11.2` last, once everything else has landed |
| `.pre-commit-config.yaml` | sync: `default_stages`, ruff `v0.16.6`, `ruff-check` id, `uv run planners validate`, `planners-index` post-merge hook |
| `.gitattributes` | merge: add `.planners/README.md merge=union`; keep the CSV `-text` rule |
| `.python-version` | identical (`3.14`) |
| `.gitignore` | merge: add `.hypothesis/`, `.vscode/`, `__pycache__/`, `dist/`, `*.egg-info/`, `.DS_Store`, `.coverage.*`; keep repo entries |
| `.claude/settings.json`, `hooks/lint-typecheck.sh` | absent, so copy (on disk only: `.claude/` is gitignored) |
| `.claude/settings.local.json` | skip: the permission baseline lives in the user-level settings, and a per-repo copy would duplicate it |
| `.claude/CLAUDE.md` | absent, so copy with the package structure and CI wording adapted to this repo (on disk only) |
| `test.yml` | sync: add the `UV_PYTHON` env and its comments, keep `--python` on `uv sync`, SHA pins to v7.0.1 / v10.2.0, `uv run pytest` (addopts carries coverage); keep the repo's `master` / `feature/**` triggers and 3.12-3.14 matrix (`requires-python >= 3.12`) |
| `publish.yml` | sync pins (checkout v7.0.1, setup-uv v10.2.0, pypi-publish v1.14.2) and header comment; keep the repo's `environment.url` |
| renovate pair | `renovate.json` identical; `renovate.yml` sync pins (checkout v7.0.1, renovate action v46.3.3) and comments |
| `.planners/` | present |
| package, `tests/`, `README.md`, `CHANGELOG.md` | never touched by the sync (code changes only for the type annotations) |

### Pyrefly strict

The default-preset config passes today. Strict over `WebSearcher/` reports 648 errors: 505
`implicit-any-type-argument` (bare `dict` / `list`), 134 `implicit-any-parameter`, 8
`implicit-any-empty-container`, and 1 `missing-override-decorator`. Decision: adopt strict and
fix every site in this PR rather than relax the preset. Annotations only; no behavior change,
which the snapshot test suite verifies.

### CI matrix caveat

The current `test.yml` lacks `UV_PYTHON`, so every matrix cell has been running `uv run` on
`.python-version` (3.14). The sync makes the 3.12 and 3.13 cells real for the first time and
may surface failures there.

### Order

1. Tooling config: `pyproject.toml`, `.pre-commit-config.yaml`, `.gitattributes`, `.gitignore`
2. CI workflows
3. Type annotations for strict pyrefly (chunked, `--no-verify` until the tree is green)
4. Coverage floor, then the `[tool.proj-template]` stamp
5. `.claude/` payload in the main checkout (untracked)
6. Verify (ruff, pyrefly, pre-commit, pytest), repair the shared git hooks, open the PR into `dev`
