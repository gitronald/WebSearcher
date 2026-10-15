---
status: draft
branch:
needs: [a, b]
---

# Upgrade selectolax to 1.0 and bump the prerelease

Part of [Upgrade selectolax to 1.0](../plan.md).

## Plan

Move to selectolax 1.0.0, make the `adopt now` changes from b, and bump the
prerelease to `0.11.7a2`.

### Steps

1. In `pyproject.toml` replace the bound with `"selectolax>=1.0.0"`, then:

   ```bash
   uv lock --upgrade-package selectolax
   uv sync --all-groups
   uv run python -c "import selectolax; print(selectolax.__version__)"   # 1.0.0
   ```

   Commit `pyproject.toml` and `uv.lock` on their own, before any code change, so
   the dependency move and our changes can be bisected apart.
2. Run `uv run pytest` on the bare upgrade. If a snapshot changes, stop and match
   it to a release-note item from b before going further (umbrella decision 5).
   Fix at the source, in the `_slx.py` helper or the parser that produced it, not
   by post-processing the output. Record each diagnosis in the Log.
3. Make each `adopt now` change from b's Findings as its own commit, and remove any
   workaround b found dead. Run `uv run pytest` after each.
4. Run the project checks and fix what they report:

   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run pyrefly check
   ```

5. Add to `CHANGELOG.md` under `## [Unreleased]`: the dependency now requires
   `selectolax>=1.0.0`, and the upstream release removed the Modest backend, so
   code that imports `selectolax.parser` directly breaks. Keep the README's Recent
   Changes for release time.
6. Bump the prerelease: `stanza release prerelease -y` (`0.11.7a1 -> 0.11.7a2`).
7. Push the branch and open the draft PR into `dev` if `/planners implement` has
   not already opened it.

### Done when

- `uv.lock` resolves selectolax 1.0.0 and the version reads `0.11.7a2`.
- The full suite passes; every snapshot change, if any, has a diagnosis in the Log.
- ruff and pyrefly are clean, and CI is green on 3.12, 3.13, and 3.14.

## Log
