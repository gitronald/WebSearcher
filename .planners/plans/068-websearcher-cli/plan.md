---
id: 68
slug: websearcher-cli
status: draft
branch: feature/websearcher-cli
created: 2026-10-28T13:55:02-07:00
concluded:
pr:
---

# Add a websearcher command with a demo group

## Plan

### Goal

Expose the packaged demos as `websearcher demo <cmd>` (`search`, `searches`, `parse`,
`show`, `headers`, `locations`) under a top-level `websearcher` console command, so the
package has one command named after itself that later, non-demo groups can join. `ws-demo`
stays for one release cycle as a deprecated alias and is removed in a later release.

### Background

`ws-demo` was chosen in plan 037 over a bare `ws`/`demo` to avoid the last-one-wins
console-script collision of a generic name. `websearcher` keeps that property (it is the
distribution's own name) and reads as a normal tool CLI.

Current wiring:

- `pyproject.toml` `[project.scripts]`: `ws-demo = 'WebSearcher.demos:main'`
- `WebSearcher/demos/cli.py`: `main()` builds one `argparse` parser (`prog="ws-demo"`) with
  the six subcommands, validates the patchright-only flags, and dispatches
- `python -m WebSearcher.demos` runs the same `main()` (`WebSearcher/demos/__main__.py`)

Repro of the current state:

```bash
uv run ws-demo --help
uv run ws-demo show --list
uv run python -m WebSearcher.demos show --list
```

### Decisions

1. **Split the demo parser so it can be mounted.** In `WebSearcher/demos/cli.py`, factor the
   subcommand definitions into `add_demo_commands(sub)` (takes a subparsers action) and the
   dispatch into `run_demo(args, parser)`. `main()` keeps its signature and behavior, built
   on those two.
2. **New `WebSearcher/cli.py`** with `main(argv=None)`: `prog="websearcher"`, a required
   subcommand, and a `demo` group whose subparsers come from `add_demo_commands`. Only `demo`
   exists for now. Add `WebSearcher/__main__.py` so `python -m WebSearcher` runs it.
3. **Console scripts**: add `websearcher = 'WebSearcher.cli:main'`; keep
   `ws-demo = 'WebSearcher.demos:deprecated_main'`.
4. **Deprecated alias**: `deprecated_main` prints one line to stderr,
   `ws-demo is deprecated and will be removed in a future release; use: websearcher demo <cmd>`,
   then runs the same dispatch with the same arguments. Help text uses `prog="ws-demo"` so its
   usage lines stay correct. `python -m WebSearcher.demos` keeps working without the notice
   (it is not the deprecated command name). Stderr, not `warnings.warn`: a
   `DeprecationWarning` is hidden by default outside `__main__`, and a CLI user should see it.
5. **Output is unchanged**: every subcommand's flags, defaults, and output stay byte-identical;
   only the command prefix changes.
6. **References**: user-facing current-tense references move to `websearcher demo ...`:
   README (Usage, profile sections), `WebSearcher/demos/__init__.py` docstring,
   `WebSearcher/demos/cli.py` docstrings, the hint in `WebSearcher/demos/show.py`
   (`Run \`ws-demo search ...\` first`), `.claude/CLAUDE.md` tree, and the repo skills
   (`.claude/skills/README.md`, `compare-parsed`, `explore-ai-overview`, `serp-inspect`,
   `update-readme-demo` and its `update_readme_demo.py`). Past CHANGELOG entries and earlier
   plans are history and keep `ws-demo`.
7. **CHANGELOG** `[Unreleased]`: an `Added` entry for `websearcher demo` and a `Deprecated`
   entry for `ws-demo`.

### Tests

- `websearcher demo show --list` and `ws-demo show --list` give the same stdout
  (`capsys`, against a temp data dir).
- `deprecated_main` writes the notice to stderr; `websearcher` and `python -m WebSearcher.demos`
  do not.
- `websearcher` with no subcommand, and `websearcher demo` with none, exit 2 with usage.
- The patchright-only flag check still fires under `websearcher demo search ... requests
  --leave-open`.
- `tests/test_profiles.py` imports `WebSearcher.demos.cli`; keep it passing, and point any
  command-line call it makes at the new entry.

### Order

1. Refactor `demos/cli.py` (decision 1), with existing tests green.
2. Add `WebSearcher/cli.py`, `WebSearcher/__main__.py`, the console scripts, and
   `deprecated_main` (decisions 2 to 4), with the new tests.
3. Update references and the CHANGELOG (decisions 6 and 7).
4. Verify:

```bash
uv sync
uv run websearcher --help
uv run websearcher demo --help
uv run websearcher demo show --list
uv run ws-demo show --list          # notice on stderr, same stdout
uv run python -m WebSearcher demo show --list
uv run pytest
```

### Out of scope

- Removing `ws-demo` (a later release, once this one has shipped).
- Any non-demo `websearcher` group.
- Regenerating the README demo output block (its `v0.11.6` header is stale independently;
  `update-readme-demo` handles it once its script emits the new command).
