---
status: draft
branch: claude/automate-locations-download
created: 2026-05-31T00:45:35-07:00
completed:
pr:
---

# Automate the Locations CSV Download

## Goal

Run a weekly job that downloads Google's latest geotargets ("locations") CSV,
tracks its contents in the repo, and overwrites the existing tracked file so the
git history captures how the CSV changes over time. Surface each change as a PR.

## Why

`WebSearcher.locations.download_locations` already fetches the geotargets CSV,
but it is built for *ad-hoc, version-pinned* use, not change tracking:

- It writes a **dated filename** (`geotargets-YYYY-MM-DD.csv`) derived from the
  upstream link, and **skips the download entirely if that file already exists**
  ("Version up to date"). So re-running never overwrites — it accumulates dated
  files or no-ops.
- Output lands in `data/`, which is **gitignored** (`.gitignore:8`), so nothing
  is tracked in git today.
- The CSV is **not bundled** in the wheel/sdist (`pyproject.toml` ships only
  `WebSearcher/`, `scripts/`, `CHANGELOG.md`). Consumers download it themselves.

To "track changes and overwrite," we need: (a) a single stable tracked path,
(b) a download path that always overwrites that file, and (c) a scheduled runner
that commits/PRs the diff.

## Decisions

- **Tracked file location: `data/locations/geotargets.csv` (repo-only, not
  bundled).** Recommendation, chosen to keep the shipped artifact small. The
  geotargets CSV is a few MB and is a moving target; bundling it would bloat
  every wheel/install with data that goes stale between releases. Tracking it in
  the repo gives the desired change history without touching the distribution.
  The package keeps downloading on demand exactly as it does now. This requires
  un-ignoring just that one path in `.gitignore` (e.g. `data/` stays ignored,
  add `!data/locations/` + `!data/locations/geotargets.csv`).
- **Change handling: open a PR.** The weekly job commits the refreshed CSV to a
  bot branch and opens/updates a PR so geo changes are reviewed (and run through
  CI) before landing, rather than pushing straight to a protected branch.
- **Mechanism: GitHub Actions cron.** A scheduled workflow under
  `.github/workflows/`, consistent with the existing `test.yml` / `publish.yml`
  (Actions + `astral-sh/setup-uv`).

## Plan

### 1. Add a stable, overwriting download mode

Add a function (or a flag on `download_locations`) that always writes to one
fixed path and overwrites it, instead of the dated-filename + skip-if-exists
behavior. Sketch:

```python
def update_locations_file(
    fp: str | Path = "data/locations/geotargets.csv",
    url: str = "https://developers.google.com/adwords/api/docs/appendix/geotargeting",
) -> Path:
    """Download the latest geotargets CSV and overwrite ``fp`` in place."""
```

- Reuse the existing `get_latest_url` / zip-vs-csv handling and `write_csv`.
- Normalize output deterministically so an unchanged upstream CSV produces a
  byte-identical file (stable row order — upstream is already Criteria-ID
  ordered — consistent newline/quoting via the existing `csv.writer`). This is
  what makes "no real change => empty git diff => no PR" work.
- Keep the current `download_locations` behavior intact (back-compat); the new
  mode is additive. Decide during implementation whether to expose it as a new
  public name in `WebSearcher/__init__.py` or keep it script-internal.

### 2. CLI entry point

`scripts/update_locations.py` (mirrors the other `scripts/` demos): calls the
overwriting function against the tracked path and prints a short summary (row
count, whether the file changed). Optionally add a `console.scripts` entry like
the existing `demo-search`.

### 3. Track the file in git

- `.gitignore`: keep `data/` ignored but un-ignore `data/locations/` and the
  `geotargets.csv` inside it.
- Commit an initial `data/locations/geotargets.csv` so the first scheduled run
  produces a reviewable *diff* rather than a whole-file add.

### 4. Scheduled workflow

`.github/workflows/update-locations.yml`:

- `on: schedule: - cron: "0 6 * * 1"` (weekly, Monday 06:00 UTC) + a
  `workflow_dispatch` for manual runs.
- Steps: `actions/checkout` -> `astral-sh/setup-uv` -> run the update script ->
  open/update a PR with the change.
- Use `peter-evans/create-pull-request` (or an equivalent) so re-running updates
  the same PR instead of stacking new ones; if the CSV is unchanged the action
  is a no-op (no empty PR).
- `permissions: contents: write, pull-requests: write`. Branch e.g.
  `bot/locations-update`; label the PR (e.g. `data`, `automated`).
- Network note: the job reaches out to `developers.google.com`; the runner has
  open egress, so no allowlist concerns in CI.

### 5. Tests / verification

- Unit-test the overwriting function with a mocked HTTP response (both the
  plain-CSV and the `.zip` upstream variants) asserting it writes the fixed path
  and that identical input yields a byte-identical file (the determinism that
  keeps no-op runs from generating PRs).
- Keep the existing `download_locations` tests/behavior green.
- Manually trigger the workflow once via `workflow_dispatch` to confirm the
  end-to-end PR flow.

## Open questions

- **PR base branch** for the automated update — `feature/v0.9.0` for now, or the
  eventual default branch (`master`/`dev`) once 0.9.0 lands?
- **Schema drift:** if Google ever changes the CSV columns, downstream
  (`demo_locations` expects `Criteria ID`, `Name`, `Canonical Name`, `Parent ID`,
  `Country Code`, `Target Type`, `Status`). The PR review is the safety net; do
  we also want a column-header assertion in the update script that fails loudly
  on drift?
- **Public API:** expose the new overwriting function in `WebSearcher/__init__`
  alongside `download_locations`, or keep it script-only?

## Out of scope

- Bundling the CSV into the wheel/sdist (explicitly rejected to keep shipped
  size down).
- Changing how `convert_canonical_name_to_uule` / search localization consume
  the CSV.

## Log - 2026-06-07

We should capture the file's name in the automated commit message - the filename contains the actual update date, not the arbitrary day we caught it and pulled it in.

