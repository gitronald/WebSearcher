---
id: 50
slug: move-parsers-to-package
status: active
branch: feature/move-parsers-to-package
created: 2026-06-20T23:11:52-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/172
---

# Move parsers.py into a parsers/ package

## Plan

### Goal

Promote the flat parse-pipeline modules into a single `WebSearcher/parsers/`
package, mirroring the recent `searchers.py` -> `searchers/` rename
(`2eb35c3`, `bce25d3`, `6373c04`). Collect the parse-time modules that currently
sit loose at the package root — `parsers.py`, `components.py`,
`component_types.py`, `bench.py` — plus the `component_parsers/` directory, under
one namespace. Pure relocation + import rewrites; **no behavior change** and **no
public-API change** (`ws.parse_serp` and `WebSearcher/__init__.py` stay byte-for-byte).

### Target layout

```
WebSearcher/parsers/
  __init__.py          # re-exports parse_serp (public surface; mirrors searchers/__init__.py)
  parsers.py           # parse_serp                       (was WebSearcher/parsers.py)
  component.py         # Component                         (from WebSearcher/components.py)
  component_list.py    # ComponentList + _last_descendant  (from WebSearcher/components.py)
  component_types.py   # unchanged content                (was WebSearcher/component_types.py)
  bench.py             # dev tool; path + module-string fixes (was WebSearcher/bench.py)
  components/          # was WebSearcher/component_parsers/
    __init__.py
    ads.py  knowledge.py  ...  (all 50 parser modules unchanged in name)
```

### Key decision: splitting `components.py`

`component_parsers/` -> `parsers/components/` (a directory) collides with
`components.py` -> `parsers/components.py` (a module): Python cannot hold both in
one package. Resolution (chosen): **split `components.py` into two modules** so
the `components/` name is free for the parser directory:

- `parsers/component.py` — the `Component` class.
- `parsers/component_list.py` — the `ComponentList` class **and** the
  module-level `_last_descendant` helper (only `ComponentList.reorder_by_dom_position`
  uses it).

This also reads cleanly: `component.py` defines `Component`, `component_list.py`
defines `ComponentList`, and `components/` holds the per-type parser functions.

### Public API is unchanged

These two consumer lines keep working **with no edit** because `parsers` becomes a
package that re-exports `parse_serp`:

- `WebSearcher/__init__.py:9` — `from .parsers import parse_serp` resolves to the
  new `parsers/__init__.py` re-export.
- `WebSearcher/searchers/searchers.py:4` — `from .. import logger, parsers, utils`
  then `parsers.parse_serp(...)` (line 149) resolves the same way.

`Component`, `ComponentList`, and the `component_types` helpers are **internal**
(not in `WebSearcher/__init__.py`'s `__all__`), so moving them is not a public
break. Downstream dict-style consumers (e.g. SearchAudits) touch parsed-result
*dicts* and `parse_serp` / `SearchEngine`, none of which change.

### Import-rewrite rule (depth changes)

Every moved module drops one level deeper, so root-level relative imports gain a
dot. The one subtlety: `component_types` moves *with* the parser dir, so
references to it from inside `components/` do **not** change.

**`parsers/parsers.py`** (was `parsers.py`):
- `from . import utils` -> `from .. import utils`
- `from .component_parsers.ai_overview import raw_serp_html` -> `from .components.ai_overview import raw_serp_html`
- `from .extractors import Extractor` -> `from ..extractors import Extractor`
- `from .extractors.extractor_serp_features import FeatureExtractor` -> `from ..extractors.extractor_serp_features import FeatureExtractor`
- `from .logger import Logger` -> `from ..logger import Logger`

**`parsers/component.py`** (the `Component` half of `components.py`):
- `from ._slx import get_text` -> `from .._slx import get_text`
- `from .classifiers import ClassifyFooter, ClassifyMain` -> `from ..classifiers import ClassifyFooter, ClassifyMain`
- `from .component_parsers import (footer_parser_dict, header_parser_dict, main_parser_dict, parse_unknown)` -> `from .components import (...)`
- `from .logger import Logger` -> `from ..logger import Logger`
- `from .models.data import (...)` -> `from ..models.data import (...)`

**`parsers/component_list.py`** (new; the `ComponentList` + `_last_descendant` half):
- add `from selectolax.lexbor import LexborNode as Node` (used by `_last_descendant`)
- add `from .component import Component` (used by `add_component`)
- no `Logger`/`get_text`/models imports — `ComponentList` uses none of them.

**`parsers/component_types.py`**: stdlib-only (`dataclasses`, `typing`) — **no change**.

**`parsers/components/*.py`** (was `component_parsers/*.py`) — mechanical, one rule:
- `from .._slx ...`   -> `from ..._slx ...`     (add a dot)
- `from ..utils ...`  -> `from ...utils ...`    (add a dot)
- `from ..models...`  -> `from ...models...`    (add a dot)
- `from ..component_types ...` -> **unchanged** (component_types is now a sibling at `parsers/`)
- `from .<sibling> ...` (e.g. `.ads`, `._common`, `._video_card`) -> **unchanged**

  This applies to `components/__init__.py` too: its `from ..component_types import
  Section, types_in_section` stays as-is; it has no `.._slx`/`..utils` lines of its own.

**`parsers/__init__.py`** (new), mirroring `searchers/__init__.py`:
```python
from .parsers import parse_serp

__all__ = ["parse_serp"]
```
Keep it minimal (parse_serp only). Internal cross-package consumers import the
submodule directly (below) rather than going through this re-export, to avoid any
package-init ordering surprises.

### In-package consumers to update (outside `parsers/`)

- `WebSearcher/extractors/__init__.py:4` — `from ..components import ComponentList`
  -> `from ..parsers.component_list import ComponentList`
- `WebSearcher/classifiers/main.py:7` — `from ..component_types import header_text_to_type`
  -> `from ..parsers.component_types import header_text_to_type`

(Importing these submodules directly is deliberate: `from X.Y.Z import name`
imports submodule `Z` without requiring `parsers/__init__.py` to have finished,
so the `parsers/__init__ -> parsers.parsers -> extractors -> parsers.component_list`
chain has no init-order cycle. Verify with a fresh `import WebSearcher` — see Verification.)

### `bench.py` special fixes (beyond import depth)

`bench.py` has no relative imports (`import WebSearcher as ws`), but two things
break on the move one level deeper:

1. `REPO_ROOT = Path(__file__).resolve().parent.parent` (line 41) -> add one
   `.parent`: `Path(__file__).resolve().parent.parent.parent`. From
   `WebSearcher/parsers/bench.py`, three parents reach the repo root.
2. Module-path strings: docstring lines 18-19 and `prog="WebSearcher.bench"`
   (line 252) -> `WebSearcher.parsers.bench`. Invocation becomes
   `uv run python -m WebSearcher.parsers.bench`.

### Config + docs

- `pyproject.toml:74` coverage omit: `"WebSearcher/bench.py"` ->
  `"WebSearcher/parsers/bench.py"` (the `searchers/*_searcher.py` entry stays).
- `pyproject.toml:46` comment: `python -m WebSearcher.bench --profile` ->
  `python -m WebSearcher.parsers.bench --profile`.
- `README.md:239-246` — the four `/component_parsers/...` mentions ->
  `/parsers/components/...`.
- No packaging change: hatchling's wheel target ships the whole `WebSearcher`
  package, so the new `parsers/` and `parsers/components/` subpackages are picked
  up automatically; `[tool.hatch.build.targets.sdist].only-include` already lists
  `"WebSearcher"`. `pyrefly` `project-includes` and `ruff` `known-first-party`
  both target `WebSearcher` — unchanged.
- **Do not** edit `.planners/plans/*` historical references to
  `WebSearcher/component_parsers/...` (plans 000, 006, 018, 019, 022, 044) — they
  are records of what was true then.

### Tests to update (mechanical)

11 test files import the moved modules. Two rename rules + one split:
- `WebSearcher.component_parsers` -> `WebSearcher.parsers.components`
  (`test_local_results`, `test_video_card`, `test_component_types`,
  `test_knowledge_rhs_facts`, `test_timestamp`, `test_ai_overview_payloads`,
  `test_knowledge_dispatch`, `test_ads`, `test_details_schema`)
- `WebSearcher.component_types` -> `WebSearcher.parsers.component_types`
  (`test_component_types`, `test_local_results`)
- `from WebSearcher.components import Component, ComponentList` splits:
  - `test_components.py` -> `from WebSearcher.parsers.component import Component`
    **and** `from WebSearcher.parsers.component_list import ComponentList`
  - `test_extractor_main.py` -> `from WebSearcher.parsers.component_list import ComponentList`

### Git mechanics (preserve history)

`WebSearcher/parsers.py` (file) and `WebSearcher/parsers/` (dir) do not collide —
different names (`parsers.py` vs `parsers`) — so a single `git mv` works:

```bash
git mv WebSearcher/parsers.py        WebSearcher/parsers/parsers.py
git mv WebSearcher/component_parsers WebSearcher/parsers/components
git mv WebSearcher/component_types.py WebSearcher/parsers/component_types.py
git mv WebSearcher/bench.py          WebSearcher/parsers/bench.py
git mv WebSearcher/components.py      WebSearcher/parsers/component.py   # then split out component_list.py
```

`component.py` shows as a rename-with-edits of `components.py` (the `ComponentList`
+ `_last_descendant` block is removed and re-created in the new
`component_list.py`); that's expected and fine.

### Implementation order

1. `git mv` the five paths above; create `WebSearcher/parsers/__init__.py`.
2. Split: cut `ComponentList` + `_last_descendant` (+ the `Node` import) out of
   `parsers/component.py` into new `parsers/component_list.py` with
   `from .component import Component`.
3. Rewrite imports inside the moved modules per the depth rule (parsers.py,
   component.py, component_list.py, every file under `components/`).
4. Apply `bench.py` `REPO_ROOT` + module-string fixes.
5. Update the two in-package consumers (`extractors/__init__.py`,
   `classifiers/main.py`).
6. Update the 11 test files.
7. Update `pyproject.toml` (coverage omit + comment) and `README.md`.
8. Verify (below).

### Verification

```bash
uv run python -c "import WebSearcher as ws; print(ws.parse_serp.__module__)"   # fresh import: no circular-import error
uv run pytest -q                                                               # full suite green
uv run python -m WebSearcher.parsers.bench --iterations 5 --runs 1 --no-save   # bench still finds tests/fixtures (REPO_ROOT correct)
```
Then run the `/lint-and-typecheck` skill (ruff + pyrefly) — pyrefly should report
no new unresolved-import errors, and ruff isort should leave the rewritten
relative imports stable.

### Out of scope

- No parser logic, classifier, or extractor behavior changes.
- No public-API additions (do not export `Component`/`ComponentList`/`component_types`
  from `WebSearcher/__init__.py`).
- No splitting/merging of individual parser modules under `components/`.
- No CHANGELOG/README "Recent Changes"/version bump here — fold into the release
  that ships this (handled per the repo's release workflow), as the searchers
  rename did (`6373c04`).

## Log

### 2026-06-20 — Implemented (PR #172)

Done in worktree `.worktrees/move-parsers-to-package` off `dev`. Followed the
plan's order exactly; the `git mv` step needed `mkdir -p WebSearcher/parsers`
first (`git mv` does not create the destination directory). The depth bump under
`components/` was a single `sed` pass (`.._slx`/`..utils`/`..models` -> `...`;
`..component_types` left untouched), verified with grep for stray 2-dot and
4-dot imports.

**Deviation — circular import (the risk the plan flagged, now resolved).** A
fresh `import WebSearcher` failed:
`classifiers/main.py` -> `from ..parsers.component_types import ...` runs
`parsers/__init__.py`, which (as first drafted) eagerly imported `parse_serp` ->
`extractors` -> `component_list` -> `component` -> back into the
half-initialized `classifiers` package -> `ImportError`. Fix: `parsers/__init__.py`
now lazy-loads `parse_serp` via PEP 562 `__getattr__` (mirroring how
`WebSearcher/__init__.py` lazy-loads `SearchEngine`), so importing a leaf
submodule no longer pulls the full pipeline. Both `from .parsers import
parse_serp` and the `parsers.parse_serp` attribute access (searchers.py) resolve
fine because by the time `WebSearcher/__init__.py` reaches them, `classifiers` is
fully initialized.

Also caught two Sphinx `:mod:` docstring cross-references the plan's grep missed
(`component_types.py`, `components/products.py`) and updated them.

**Verification:** 537 tests + 87 snapshots pass; `ruff check` clean (4 import-order
auto-fixes applied); `pyrefly check` 0 errors; fresh import + parse smoke OK;
`python -m WebSearcher.parsers.bench` resolves `tests/fixtures/` (REPO_ROOT depth
fix confirmed).

### 2026-06-21 — Replaced the `__getattr__` workaround with the structural fix (Option A)

PR review (`.claude/scratch/pr172-review.md`) flagged the `__getattr__` lazy-load
as a band-aid that papered over a layering inversion: the leaf modules
(`component`, `component_list`, `component_types`, `components/`) are imported by
`extractors`/`classifiers` *below* the orchestrator (`parsers.parsers`), so
re-exporting `parse_serp` from `parsers/__init__.py` made importing any leaf drag
the orchestrator in mid-init. The `__getattr__` only existed to preserve the
`WebSearcher.parsers.parse_serp` **attribute**, which resolved incidentally back
when `parsers.py` was a module.

Adopted **Option A**: stop surfacing `parse_serp` through the package `__init__`
entirely, so there is no edge to defer.
- `parsers/__init__.py` -> docstring only; dropped `__getattr__`/`__dir__`/`__all__`.
- `WebSearcher/__init__.py`: `from .parsers.parsers import parse_serp` (was `from .parsers import parse_serp`).
- `searchers/searchers.py`: dropped `parsers` from `from .. import ...`, added
  `from ..parsers.parsers import parse_serp`, and call `parse_serp(...)` directly
  (was `parsers.parse_serp(...)`).

**Downstream gate cleared:** confirmed the public consumer (the SearchAudits
crawl/analysis code) only calls top-level `ws.parse_serp(...)` (kept intact) and
never touches the `WebSearcher.parsers.parse_serp` attribute — its two
`WebSearcher.parsers` references are logger-name strings, not imports.

**Verification:** fresh top-level import OK (`ws.parse_serp.__module__ ==
WebSearcher.parsers.parsers`); leaf-first import (`import
WebSearcher.parsers.component_types` then `...component_list`) no longer cycles;
`hasattr(WebSearcher.parsers, 'parse_serp')` is now `False` (expected); 537 tests
+ 87 snapshots pass; `ruff check` clean; `pyrefly check` 0 errors.

