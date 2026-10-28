---
id: 65
slug: keep-every-geotargets-release
status: active
branch: feature/keep-every-geotargets-release
created: 2026-10-27T11:46:08-07:00
concluded:
pr:
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

- Releases older than 2026-07-16: the ledger up to 2026-06-15 is the seeded archive and is
  complete.
- The branch-from-master, PR-to-dev arrangement, which stays as plan 031 set it.

## Log

- **2026-10-28T09:39:35-07:00** — Activated.
  - Branch: `feature/keep-every-geotargets-release`
  - Base: `dev` at `8b5ae40`
  - Worktree: `.worktrees/065-keep-every-geotargets-release`
  - PR: pending
