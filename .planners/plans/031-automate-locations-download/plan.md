---
id: 31
slug: automate-locations-download
status: done
branch: feature/v0.10.0-locations-download
created: 2026-05-31T00:45:35-07:00
concluded: 2026-06-10T21:20:42-07:00
pr: https://github.com/gitronald/WebSearcher/pull/169
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
- **Change detection: upstream filename via a ledger, not byte-diffing.** Each
  successful download appends a row to a git-tracked ledger
  (`data/locations/ledger.csv`) recording the date collected and the upstream
  filename. The filename — not the collection date — is the version identity:
  it embeds the real release date (`geotargets-YYYY-MM-DD.csv`), while the
  collection date is just whenever our job happened to catch it. The weekly job
  compares the latest upstream filename against the ledger's last row and skips
  the download when they match, so unchanged upstream => no download, no diff,
  no PR. Byte-level determinism (step 1) becomes a backstop rather than the
  load-bearing mechanism.
- **Seed history from the existing archive.** `data/google_locations/`
  (gitignored) holds 26 manual pulls spanning 2018-09-04 -> 2026-02-25 with
  their upstream filenames preserved. Replay them chronologically onto the
  tracked path — one commit per snapshot — so the tracked file's git history
  starts in 2018 rather than at automation start (step 3).

## Plan

### 1. Add a stable, overwriting download mode with a ledger

Add a function (or a flag on `download_locations`) that always writes to one
fixed path and overwrites it, instead of the dated-filename + skip-if-exists
behavior, and records each successful pull in the ledger. Flow:

1. `get_latest_url(url)` -> extract the upstream filename (e.g.
   `geotargets-2026-02-25.csv`).
2. If that filename matches the ledger's last `filename`, stop — already
   current (no download, no diff, no ledger row).
3. Otherwise download, overwrite `data/locations/geotargets.csv`, and append a
   row to `data/locations/ledger.csv`.

Sketch:

```python
def update_locations_file(
    fp: str | Path = "data/locations/geotargets.csv",
    ledger_fp: str | Path = "data/locations/ledger.csv",
    url: str = "https://developers.google.com/adwords/api/docs/appendix/geotargeting",
) -> str | None:
    """Download the latest geotargets CSV, overwrite ``fp``, and log the pull.

    Returns the upstream filename if a new version was pulled, else None.
    """
```

**Ledger spec** (`data/locations/ledger.csv`, git-tracked, append-only — one
row per successful download):

| column           | meaning                                                       |
|------------------|---------------------------------------------------------------|
| `date_collected` | date the job pulled the file (the run date)                   |
| `filename`       | upstream filename as published — embeds the real release date |

The two dates genuinely differ (e.g. a run on 2026-06-15 would still pull
`geotargets-2026-02-25.csv`), which is why both are recorded. Rows seeded from
the archive backfill (step 3) leave `date_collected` empty: the original pull
dates were never recorded, and the archive files' mtimes are copy timestamps,
not collection dates.

- Reuse the existing `get_latest_url` / zip-vs-csv handling and `write_csv`.
- Normalize output deterministically so an unchanged upstream CSV produces a
  byte-identical file (stable row order — upstream is already Criteria-ID
  ordered — consistent newline/quoting via the existing `csv.writer`). With the
  ledger doing change detection this is a backstop, not load-bearing; it is
  already true today (see step 3 verification).
- Keep the current `download_locations` behavior intact (back-compat); the new
  mode is additive. Decide during implementation whether to expose it as a new
  public name in `WebSearcher/__init__.py` or keep it script-internal.

### 2. CLI entry point

`scripts/update_locations.py` (mirrors the other `scripts/` demos): calls the
overwriting function against the tracked path and prints a short summary (the
upstream filename, row count, and whether a new release was pulled). Optionally
add a `console.scripts` entry like the existing `demo-search`.

### 3. Track the file in git and seed its history from the archive

- `.gitignore`: keep `data/` ignored but un-ignore `data/locations/` and the
  two tracked files inside it (`geotargets.csv`, `ledger.csv`).
  `data/google_locations/` (the bz2 archive) stays untracked.
- `.gitattributes`: mark `data/locations/*.csv -text`. The CSVs are
  CRLF-terminated (`csv.writer`'s default `\r\n`); without this, git's
  line-ending normalization could rewrite or warn on them and break the
  byte-faithful diff story.

**Seed the history.** Instead of committing a single initial CSV, replay the
existing manual-pull archive so the tracked file carries eight years of real
history before automation takes over:

- Corpus: 26 bz2 snapshots in `data/google_locations/`, upstream filenames
  preserved exactly as downloaded — `AdWords API Location Criteria
  2018-09-04.csv.bz2` (old AdWords-era shape), then `geotargets-YYYY-MM-DD
  .csv.bz2` from 2019 on. `data/locations/geotargets-2026-02-25.csv` is the
  uncompressed latest and is byte-identical to its bz2 copy, so the bz2 corpus
  alone suffices.
- One-off seeding script: for each snapshot in release-date order — parse the
  date from the filename (handle both name shapes), decompress, round-trip
  through the same csv normalization the downloader uses, write
  `data/locations/geotargets.csv`, append a ledger row (`date_collected`
  empty, `filename` without the `.bz2` suffix), then `git add` + commit as
  `update locations: geotargets-YYYY-MM-DD`.
- After the last replayed commit the working tree holds exactly what a fresh
  download of the current release writes, so the first automated run no-ops
  cleanly via the ledger check.
- Repo-size note: the snapshots sum to ~37 MB bz2-compressed (~900 KB in 2018
  to ~2.2 MB in 2026; ~17 MB uncompressed latest), but consecutive versions
  are highly similar, so git's delta compression should land the actual repo
  growth well below that sum.

Verified against the corpus (2026-06-10, repo root):

```bash
# Schema stable 2018 -> 2026: identical 7-column header text in all 26
# snapshots (sort -u yields the same line twice, differing only in \r)
for f in data/google_locations/*.bz2; do bzcat "$f" | head -1; done \
  | tr -d '\r' | sort -u
# -> Criteria ID,Name,Canonical Name,Parent ID,Country Code,Target Type,Status

# Line endings are MIXED across the archive: LF through 2020-03-03, CRLF
# after — except 2024-08-13 and 2025-01-13, which are LF again (different
# save paths over the years). This is why the replay must normalize: without
# it, seeded diffs would show whole-file line-ending flips, not real changes.
for f in data/google_locations/*.bz2; do
  bzcat "$f" | head -1 | grep -q $'\r' && echo "CRLF  $f" || echo "LF  $f"
done

# Current pipeline output is byte-identical to the stored snapshot
bzcat data/google_locations/geotargets-2026-02-25.csv.bz2 \
  | cmp - data/locations/geotargets-2026-02-25.csv && echo IDENTICAL
```

### 4. Scheduled workflow

`.github/workflows/update-locations.yml`:

- `on: schedule: - cron: "0 6 * * 1"` (weekly, Monday 06:00 UTC) + a
  `workflow_dispatch` for manual runs.
- Steps: `actions/checkout` -> `astral-sh/setup-uv` -> run the update script ->
  open/update a PR with the change.
- Use `peter-evans/create-pull-request` (or an equivalent) so re-running updates
  the same PR instead of stacking new ones; if the CSV is unchanged the action
  is a no-op (no empty PR).
- Commit message carries the upstream filename, not the run date — e.g.
  `update locations: geotargets-2026-02-25` — since the filename embeds the
  real release date (per the 2026-06-07 log note). The PR diff includes both
  `geotargets.csv` and the appended `ledger.csv` row.
- `permissions: contents: write, pull-requests: write`. Branch e.g.
  `bot/locations-update`; label the PR (e.g. `data`, `automated`).
- Network note: the job reaches out to `developers.google.com`; the runner has
  open egress, so no allowlist concerns in CI.

### 5. Tests / verification

- Unit-test the overwriting function with a mocked HTTP response (both the
  plain-CSV and the `.zip` upstream variants) asserting it writes the fixed path
  and that identical input yields a byte-identical file (the determinism
  backstop).
- Unit-test the ledger logic: skips (no download, no ledger row) when the
  latest upstream filename matches the ledger's last row; downloads and
  appends exactly one row when it doesn't; handles an empty/missing ledger
  (first run).
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
  on drift? *Partially answered by the archive review (step 3): the header text
  has been identical across all 26 snapshots, 2018 -> 2026, so a header
  assertion is cheap and near-zero false-positive risk — lean yes.*
- **Public API:** expose the new overwriting function in `WebSearcher/__init__`
  alongside `download_locations`, or keep it script-only?

## Out of scope

- Bundling the CSV into the wheel/sdist (explicitly rejected to keep shipped
  size down).
- Changing how `convert_canonical_name_to_uule` / search localization consume
  the CSV.

## Log - 2026-06-07

We should capture the file's name in the automated commit message - the filename contains the actual update date, not the arbitrary day we caught it and pulled it in.

## Log - 2026-06-08

Before building the automation, review the manual-pull history we already have in
`data/google_locations/` (gitignored, untracked — 26 snapshots spanning
`2018-09-04` through `2026-02-25`). It's a ready-made record of how the CSV evolves:
the compressed size roughly doubles over the period (~900 KB → ~2.2 MB), and it's
the right corpus to diff across years to spot any column/schema drift before
settling the deterministic-normalization (step 1) and schema-drift (open question)
work.

Filename caveat for the "use the upstream date" idea above: the format is **not**
stable across the history. The oldest file is `AdWords API Location Criteria
2018-09-04.csv.bz2` (the old AdWords-era name, spaces and all); every file from 2019
on is `geotargets-YYYY-MM-DD.csv.bz2`. These are the upstream-provided names exactly
as downloaded — never hand-edited — so the embedded date is the real upstream
publish date, but any logic that derives the date from the filename must handle both
the `AdWords API Location Criteria <date>` and `geotargets-<date>` shapes.

## Log - 2026-06-10

Fleshed out the spec: added the ledger design (`data/locations/ledger.csv`,
`date_collected,filename` — change detection now keys on the upstream filename
rather than byte-diffing) and expanded step 3 into a full history seeding replay
of the 26-snapshot archive. Ran the archive review proposed in the 2026-06-08
log entry; results (repro commands in step 3):

- Header text identical across all 26 snapshots, 2018 -> 2026 — no schema
  drift, ever.
- Line endings are mixed (LF through 2020-03-03, CRLF after, except
  2024-08-13 and 2025-01-13 which are LF) — the replay must normalize or
  seeded diffs will be dominated by line-ending flips.
- The current pipeline's output for 2026-02-25 is byte-identical to the stored
  bz2 snapshot, so the normalization round-trip is already byte-stable.

## Log - 2026-06-10 (implementation)

Implemented on `feature/v0.10.0-locations-download`; draft PR opened against
`feature/v0.10.0` (see `pr:`). Deviations from the spec:

- The `scripts/` directory referenced in step 2 no longer exists in the repo;
  the CLI entry is a `main()` in `WebSearcher/locations.py` run as
  `python -m WebSearcher.locations`, and the one-off seeding script lives as a
  plan sidecar (`seed_history.py` in this directory) rather than under
  `scripts/`.
- `normalize_csv_text` (the shared round-trip, also adopted by
  `download_locations`) needed a trailing-newline fix: `split("\n")` on a
  newline-terminated body yields a final empty string that `csv` round-trips
  into a spurious blank row. Caught by the new unit tests.
- The seeding replay produced 26 commits (`update locations:
  geotargets-YYYY-MM-DD`); the final tracked file is byte-identical to the
  newest archive snapshot, so the first automated run no-ops via the ledger
  check. Object-store growth from the replay was ~46 MB loose (pre-delta);
  the push pack is far smaller.
- Open question "PR base branch" resolved in practice: the workflow PRs
  against the default branch it runs on (it only schedules once merged to
  master); the feature work itself targets `feature/v0.10.0`.
- Open question "public API" resolved: exported `update_locations_file` in
  `WebSearcher/__init__` alongside `download_locations`.
- The header assertion (schema-drift open question) is not implemented yet —
  left for PR review to decide; the weekly PR diff remains the primary safety
  net.

## Log - 2026-06-10 (review follow-up)

Close-gate review (7 finder angles + adversarial verification; full review
posted on the PR) produced five fixes, committed as `apply review fixes for
locations update`:

- Added `REQUEST_TIMEOUT = 60` to both `requests.get` calls — an unattended
  weekly cron must not hang on a stalled connection.
- Replaced the `split("\n")` + trailing-pop normalization with
  `csv.reader(io.StringIO(text, newline=""))`: the split form silently
  corrupted quoted fields containing newlines. Verified equal rows across all
  26 archive snapshots and byte-identical output for the latest; regression
  test added.
- Resolved the schema-drift open question as **yes**: `update_locations_file`
  now validates the downloaded header against `GEOTARGETS_HEADER` and raises
  before the ledger row is written (failed pulls retry next run); regression
  test added.
- Extracted `download_csv` to deduplicate the zip-vs-csv branch shared by
  `download_locations` and `update_locations_file`.
- Replaced the workflow's `tail | cut | tr` ledger parse with a `csv.reader`
  one-liner (csv-quoted filenames would have broken the shell parse).

Conscious no-ops (details in the PR review comment): multi-CSV zip behavior in
`save_zip_response` (pre-existing, upstream zips carry one CSV), the
`download_locations` trailing-blank-row byte change (intentional fix), `main()`
re-reading the CSV for its row-count report (negligible weekly cost), relative
default paths (matches package precedent), and test-local DictReader
repetition. Refuted by verifiers: ledger-missing-on-first-run (ledger is
committed alongside the workflow), stale release name on no-op runs
(`create-pull-request` exits silently with no changes), and corrupt-ledger
masking (`KeyError` propagates loudly).

Final gate: 514 tests pass, ruff clean, pyrefly 0 errors; CI green on the PR.

## Retrospective

- The 2026-06-08 decision to review the archive before building paid off
  twice: it surfaced the mixed LF/CRLF endings (which made normalization a
  hard requirement, not a nicety) and pre-answered the schema-drift question
  with eight years of evidence, making the header assertion a confident yes.
- Keying change detection on the upstream filename via a tracked ledger turned
  out cleaner than the original byte-determinism design — determinism became a
  backstop instead of the load-bearing mechanism, and the ledger doubles as
  the release-history record the commit messages were trying to be.
- The review gate caught a real correctness bug in code the tests already
  "covered" (quoted-newline corruption in `normalize_csv_text`) — the fix the
  unit tests drove (trailing-pop) was itself the fragile shape; the deeper
  io.StringIO form removed both the bug and the special case.
- Plans drift: step 2 referenced a `scripts/` directory that had been removed
  from the repo since the plan was drafted. Re-grounding the spec against the
  current tree at implement time (per the verify-plan-evidence memory) kept it
  a one-line adaptation instead of a mid-build surprise.
- Replaying 26 versions of a 17 MB file added ~46 MB loose objects locally but
  far less over the wire after delta compression — seeding history into git
  was cheap enough to be the right call.

