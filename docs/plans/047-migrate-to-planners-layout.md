---
id: 47
slug: migrate-to-planners-layout
status: draft
branch:
created: 2026-06-09T10:31:22-07:00
concluded:
pr:
---

# Migrate plans to the .planners layout

Move this repo from the legacy `docs/plans/{NNN}-{slug}.md` + `TODO.md` layout to the
`planners` package's `.planners/` layout, where each plan is a directory
(`.planners/plans/<NNN>-<slug>/plan.md`) and the index is the generated
`.planners/README.md`. Driven by the fleet rollout tracked in quipus plan 033 (the
standardization onto the `planners` package); this repo follows the same runbook proven on
earlier repos.

## Plan

1. **Standardize frontmatter in source.** Every legacy plan (000–046) is missing `id`/`slug`
   and uses the old `completed:` key (legacy order `status, branch, created, completed, pr`).
   Add `id` (= directory `NNN`) and `slug` (= directory slug), rename `completed:` →
   `concluded:` (hard cutover, planners ≥ 0.2.0), and normalize field order to
   `id, slug, status, branch, created, concluded, pr`. Specific fixes:
   - Plan 017 (`status: abandoned`) → `retired`: it was superseded by plan 023 (the
     profiling-first revision); both shipped under PR #125.
   - Plans 042 and 043 (`inactive`) are missing `created:` — backfill from each file's first
     git commit.
2. **Move plans into per-plan directories** — `git mv docs/plans/<base>.md
   .planners/plans/<base>/plan.md`, then `rmdir docs/plans`.
3. **Repoint in-repo references** to the moved plan paths (`docs/plans/<base>.md` →
   `.planners/plans/<base>/plan.md`), excluding `.git` and the moved plan bodies. Separate,
   clearly-labeled commit so it is easy to drop if a plan-system-only migration is preferred.
4. **Reconcile `TODO.md`.** Both current items already link existing plans (045, 046), so no
   stubs are needed — the move preserves them. `TODO.md` is then retired with `git rm`.
5. **Restore `docs/README.md` to a curated landing page.** It currently holds the generated
   plans table; `.planners/README.md` is now the generated index. Strip the table and keep a
   short curated landing page (the `docs/` tree also has `reports/`). Confirm before changing.
6. **Install the holder and wire + activate the pre-commit hook** (`planners install
   --global`, then `uv add --dev pre-commit` and `pre-commit install` for this uv project),
   run `planners validate`, and generate `.planners/README.md` with `planners index .`.

The run lands on a dedicated worktree branch via `/planners implement` and ends at a
review-ready PR via `/planners close` — stopping for user approval rather than merging.

## Log
