---
id: 47
slug: migrate-to-planners-layout
status: done
branch: plan/047-migrate-to-planners-layout
created: 2026-06-09T10:31:22-07:00
concluded: 2026-06-09T11:07:44-07:00
pr: https://github.com/gitronald/WebSearcher/pull/165
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

### 2026-06-09 — migration executed (plan/047-migrate-to-planners-layout, PR #165)

Ran on a worktree branched off `feature/v0.10.0` (the active development line, 48 commits
ahead of `dev`; chosen over `dev`/`master` so the migration covered the complete, current
plan set without later conflicts). Seven commits on the branch:

1. `move plans to .planners/ + standardize frontmatter` — all 47 legacy plans (000–046).
2. `record pr url in plan 047 frontmatter`.
3. `consolidate docs into .planners` — `reports/` moved under `.planners/`, `docs/README.md`
   removed, the emptied `docs/` dropped.
4. `retire TODO.md convention (drop gitignore entry)`.
5. `wire planners-validate pre-commit hook`.
6. `update dev-story path comment after reports move`.
7. `kebab-case slugs for 005/014 + generate index`.

**Frontmatter standardization (mechanical).** Legacy frontmatter was `status, branch, created,
completed, pr` with no `id`/`slug`. Re-emitted every plan in canonical order
`id, slug, status, branch, created, concluded, pr`: added `id` (= directory NNN) and `slug`
(= directory slug) and renamed `completed:` → `concluded:`, preserving all values (explicit
`null` on closed plans, empty pending fields on open ones).

**Review (issues raised + resolutions):**
- *Base branch* — the repo's active line is `feature/v0.10.0`, not `dev`. Confirmed with the
  user; based the migration there and targeted the PR at it.
- *Plan 017 `abandoned` → `retired`* — superseded by plan 023 (the profiling-first revision);
  both shipped under PR #125. Neutral terminal status, no failure connotation.
- *Plans 042 / 043 missing `created`* — backfilled from each file's first git commit
  (`2026-06-06T01:46:36-07:00`).
- *`docs/README.md`* — held the generated plans table (now `.planners/README.md`). Per user
  direction, moved `docs/reports/` into `.planners/reports/` and removed `docs/README.md` and
  the emptied `docs/`, consolidating all plan/doc artifacts under `.planners/`. The moved
  `get_commits.py` resolves repo root by directory depth and is unaffected by the move; only
  its stale path comment was updated.
- *`TODO.md` gitignored + untracked* — unexpected: no `git rm` was possible. Both items already
  linked tracked plans 045/046 (nothing lost). Per user direction, removed the `TODO.md` line
  from `.gitignore` (a tracked change) and deleted the local untracked file. No stubs were
  needed.
- *Non-kebab slugs (005, 014)* — `parser-updates-v0.6.7a2` and `bump-0.6.9` failed `validate`
  (version dots aren't kebab-case). Renamed directories and `slug` fields dots→hyphens
  (`parser-updates-v0-6-7a2`, `bump-0-6-9`); the only references were the auto-regenerated
  index, so nothing else needed repointing.
- *Titles* — all 47 are descriptive (no `# Plan` placeholders or `Plan:` prefixes); left as
  historical record, not re-cased.
- *In-repo plan-path references* — none existed (the lone `docs/plans/` mention is a historical
  CHANGELOG entry, left as record).

**Validation & gate:** `planners validate .planners/plans` → ok, 48 files valid. The
`planners-validate` pre-commit hook is wired and active (`pre-commit` was already a dev
dependency and the git hook already registered) and passed on the staged plans. No
package/library code changed, so ruff + pyrefly (green via pre-commit on every commit) cover
the check gate; no source-affecting changes for pytest.

**Stopped at a review-ready PR (#165)** per the migration runbook — not merged; the worktree
and branch are left in place for user approval.

## Retrospective

- The frontmatter delta was uniform and fully mechanical (every plan missing `id`/`slug` and
  using the `completed` key); a single canonical re-emit pass handled all 47, leaving only
  017's status and 042/043's `created` as per-plan judgment.
- Two surprises drove the only real decisions: `TODO.md` was gitignored/untracked (so "retire"
  meant a `.gitignore` edit + local delete, not `git rm`), and two slugs carried version dots
  that `validate` rejects — both worth probing early on future repos.
- The active line being `feature/v0.10.0` rather than `dev` mattered: basing on `dev` would
  have migrated a stale, incomplete plan set. Check branch divergence before choosing a base.
- The user redirected `docs/reports/` into `.planners/` rather than keeping a curated
  `docs/README.md`, which left `docs/` removable — a cleaner consolidation than the runbook's
  default.
- `planners validate` as the final gate caught the non-kebab slugs the mechanical pass missed —
  cheap, decisive verification that belongs at the end of every migration.
