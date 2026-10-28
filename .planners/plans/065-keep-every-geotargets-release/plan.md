---
id: 65
slug: keep-every-geotargets-release
status: implemented
branch: feature/keep-every-geotargets-release
created: 2026-10-27T11:46:08-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/214
---

# Keep every geotargets release in the locations history

## Plan

### Problem

Plan 031 tracks `data/locations/geotargets.csv` in git so that the file's history records
every upstream release, with `data/locations/ledger.csv` as the append-only record of each
pull. The weekly `update-locations.yml` job does not deliver that whenever its pull request
is not merged before Google's next release.

What happened between June and October 2026, from the job's run logs and the PR timeline:

| Weekly runs | Release the job pulled | Where it is now |
|---|---|---|
| 2026-08-03 to 2026-08-17 | `geotargets-2026-07-16` | no reachable commit, no ledger row |
| 2026-08-24 to 2026-10-12 | `geotargets-2026-08-12` | no reachable commit, no ledger row |
| 2026-10-19 to 2026-10-26 | `geotargets-2026-10-06` | merged as PR #195 on 2026-10-27 |

PR #195 was opened on 2026-07-13, force-pushed every Monday after that, and merged on
2026-10-27. The merged history goes from `geotargets-2026-06-15` straight to
`geotargets-2026-10-06`: two releases are missing from the tracked file's history and from
the ledger. The 2026-08-12 commit survives only as an unreachable object in clones that
fetched the branch during those weeks.

Three mechanisms combine:

1. **The branch never accumulates commits.** `peter-evans/create-pull-request` rebuilds
   `bot/locations-update` from the checkout on every run and force-pushes one commit
   holding the working-tree diff.
2. **Newness is judged against the checkout's ledger.** `update_locations_file` compares
   the one latest filename on Google's page to the last row of the ledger in the checkout
   (master). While the PR is unmerged that row does not move, so every run re-derives
   "latest vs. last merged", and the single commit holds only the newest release and one
   ledger row. An earlier unmerged release is replaced, not stacked.
3. **Google's page lists only two releases**, the current one and the previous one (checked
   2026-10-27), so a job that fell further behind cannot enumerate what it missed. Older
   releases are still served at the dated static URL
   `https://developers.google.com/static/google-ads/api/data/geo/geotargets-YYYY-MM-DD.csv.zip`
   (both missing ones returned 200 on 2026-10-27), but only when the date is known.

The download and header-check code is correct. The defect is an assumption plan 031 never
stated: that a person merges each PR within a week.

### Decisions

1. **Backfill the two missing releases first**, from Google's dated URLs, as commits on the
   tracked file: `geotargets-2026-07-16`, then `geotargets-2026-08-12`, then
   `geotargets-2026-10-06` again, each with the ledger ending at that release and the
   commit subject `update locations: <release>` the job uses. The commits land after the
   10-06 merge, so `git log` is not chronological there, but
   `git log -- data/locations/geotargets.csv` then shows every snapshot and the ledger reads
   06-15, 07-16, 08-12, 10-06 in release order. The backfilled rows carry the backfill date
   in `date_collected`, which is what the column means. Adapt the plan 031 sidecar
   `seed_history.py` (it replays a directory of `*.csv.bz2` snapshots, oldest first, through
   the same normalize-write-ledger-commit steps) to take the two downloads, write the
   collection date, and end by restoring 10-06.
2. **Merge the bot's PR from the workflow.** Keep the PR (it is the visible record and
   carries the `data` label) and merge it in the job right after creation with
   `gh pr merge --merge` and the repo's merge subject. No checks run on a PR opened with the
   workflow token, so there is nothing to wait for; the header check inside the job is the
   safeguard, and a ten-thousand-line CSV diff was never reviewed by eye. Switch to `--auto`
   if dev ever gets required checks. The job already has `contents: write` and
   `pull-requests: write`.
3. **Pull every listed release newer than the ledger, one commit each.** `get_latest_url`
   becomes a listing of all geotargets links on the page, sorted by date;
   `update_locations_file` pulls the oldest release newer than the ledger's last row and
   returns its filename, so a caller loops until it returns None. The workflow loops,
   committing after each pull, before `create-pull-request` runs; the action includes
   commits made earlier in the run, so the PR carries one commit per release (verify this
   against the action's documentation during implementation; the fallback is to push the
   branch with git and open the PR with `gh pr create`). With decision 2 the loop runs once
   almost every time; it matters when two releases land within one week or a run is skipped.
4. **Warn on an unenumerable gap.** When the ledger's last release is older than every
   release the page lists, the job cannot know what it missed. Print a warning naming the
   ledger's last release and the oldest listed one, so the gap shows in the run log and can
   be backfilled by hand from the dated URL.

### Files

- `WebSearcher/locations.py`: the release listing, the oldest-unseen pull, the gap warning;
  `main()` prints the pulled release or nothing.
- `.github/workflows/update-locations.yml`: the pull-and-commit loop, the merge step.
- `tests/test_locations.py`: the listing (two links, date order), the oldest-unseen choice,
  the loop reaching "up to date", the gap warning.
- `data/locations/geotargets.csv`, `data/locations/ledger.csv`: the backfill commits.
- `CHANGELOG.md`: an Unreleased entry for the updater behaviour (the backfill is data, not
  a package change).

### Order

The backfill (decision 1) first, in its own commits, so the history is complete before the
job changes. Then decisions 3 and 4 in the module with their tests, then decision 2 and the
loop in the workflow.

### Verification

- `uv run pytest tests/test_locations.py` and the project checks.
- `git log --format=%s -- data/locations/geotargets.csv` lists 2026-06-15, 2026-07-16,
  2026-08-12, and 2026-10-06 after the backfill, and the ledger ends at 2026-10-06.
- After the merge, a `workflow_dispatch` run reports up to date and opens no PR. The next
  Google release produces a PR with one commit that merges itself, and the ledger gains one
  row.

### Out of scope

- Releases older than 2022-12-21: Google's dated URLs serve nothing earlier, so gaps in the
  seeded archive before that date cannot be enumerated. (Corrected 2026-10-28: this line first
  said the seeded archive up to 2026-06-15 was complete. The probe found 15 releases missing
  from it, now backfilled; see Log.)
- The PR-to-dev arrangement, which stays as plan 031 set it. (Corrected 2026-10-28: this line
  first kept the branch-from-master half as well. The job read master's ledger, which moves
  only at a release, so merging into dev would not have stopped the re-pulls; the workflow now
  checks out dev. See Log.)

## Log

- **2026-10-28T09:39:35-07:00** — Activated.
  - Branch: `feature/keep-every-geotargets-release`
  - Base: `dev` at `8b5ae40`
  - Worktree: `.worktrees/065-keep-every-geotargets-release`
  - PR: pending
- **2026-10-28T10:17:01-07:00** — PR opened: https://github.com/gitronald/WebSearcher/pull/214
- **2026-10-28T10:17:17-07:00** — Implemented decisions 1-4, with the backfill widened from two releases to every release Google still serves.
  - Lost to the force-pushed bot branch: three releases, not two. The PR's GraphQL `HeadRefForcePushedEvent` chain (`beforeCommit`/`afterCommit`) lists all 16 weekly commits, starting with `328248f` on 2026-07-13, which pulled `geotargets-2026-07-06`; the PR was renamed 07-06 -> 07-16 on 2026-07-27, 07-16 -> 08-12 on 2026-08-24, and 08-12 -> 10-06 on 2026-10-19. Run logs from July return HTTP 410 (expired); the timeline does not.
  - Every force-pushed commit is still fetchable by SHA (`git fetch origin <sha>`). Each release's CSV blob is identical across all its weekly re-pulls, and a fresh download of 07-06, 07-16, and 10-06 through `download_csv` is byte-identical to the bot's blob, so recovered and downloaded snapshots are interchangeable.
  - The seeded archive was not complete, contrary to Out of scope. `probe_releases.py` (sidecar) sends a HEAD per day to the dated static URL: 2018-09-01 to 2026-10-28 finds 33 releases served, the oldest 2022-12-21 (nothing earlier answers). 15 of them were in neither git nor the ledger: 2023-05-03, 2023-08-21, 2024-06-12, 2024-06-19, 2024-06-28, 2024-07-11, 2025-04-01, 2025-06-26, 2025-07-15, 2026-01-22, 2026-03-23, 2026-03-31, 2026-05-05, 2026-05-14, 2026-05-28. Every ledger release from 2022-12-21 on is served. Releases before 2022-12-21 cannot be enumerated.
  - `backfill_history.py` (sidecar, adapted from plan 031's `seed_history.py`) replayed 18 releases oldest first, then restored 10-06: 3 from the bot commits (`--recovered 328248f1c8 --recovered 03bdb35782 --recovered 7c233c46eb`), keeping the job's `date_collected` (2026-07-13, 2026-07-27, 2026-08-24) and author date; 15 downloaded (`--download <date>`), with the backfill date 2026-10-28. The ledger at each commit is the final ledger cut at that release. Checked: the tip CSV equals the pre-backfill blob, the ledger diff is 18 added rows and no removed ones, release order holds, and `git log --format=%s -- data/locations/geotargets.csv` lists 47 snapshots. The 10-06 row keeps its merged `2026-10-26` date (first pulled 2026-10-19).
  - Deviation, workflow: decision 2 alone does not move the ledger the job reads. The job checked out master, whose ledger ends at 06-15 and moves only at a release, while PRs merge into dev. The workflow now checks out `ref: dev`, which the plan had listed as out of scope.
  - Module: `get_release_urls` lists dated release links only. The live page also links itself (`/google-ads/api/data/geotargets`), which the old lexical sort skipped only by accident. `release_date` reads both filename shapes. `update_locations_file` pulls the oldest unseen release and prints the gap warning; `get_latest_url` is the last listed release.
  - Workflow: a bounded loop (6 runs) commits each pull as `update locations: <release>` under the `github-actions[bot]` identity. `create-pull-request` carries those commits; its v8.1.1 README lists "commits made during the workflow that have not been pushed" among the changes it includes. The job polls `mergeable` and then runs `gh pr merge --merge --delete-branch --subject "merge: PR #<n> - bot/locations-update"`.
  - Checks: 875 tests pass (coverage 85.13%), ruff and pyrefly clean, and the listing was run live against the page (returns 08-12 and 10-06).
- **2026-10-28T10:19:21-07:00** — Implemented: 26 commits ahead of `dev`.

## Handoff

State: all work is committed and pushed on `feature/keep-every-geotargets-release`, with PR #214 against dev.

Not verified:

- The new workflow has not run. `create-pull-request` keeping one commit per release, and the in-job merge, are taken from the action's README and not observed. The first `workflow_dispatch` on dev after the merge (`gh workflow run update-locations.yml --ref dev`) should report up to date and open no PR.
- Scheduled runs read the workflow file from master, so until the next stable release the Monday job still runs the old workflow against master's ledger, which ends at 06-15. Its next run (2026-11-02 06:00 UTC) will try to land 10-06 against dev's backfilled ledger. Expect a failed run or a bot PR whose ledger diff drops or reorders rows. Close such a PR unmerged. A release before that date avoids it.

Questions:

1. Should the plan's Out of scope line ("the ledger up to 2026-06-15 is the seeded archive and is complete") be corrected in the spec, or left as the record of what was believed? The Log carries the correction (15 missing releases found and backfilled). **Answered 2026-10-28: correct it.** Done in Out of scope.
