"""One-off: backfill geotargets releases missing from the tracked history.

The tracked file's history lost releases two ways: the weekly job's force-pushed
PR branch replaced releases that were never merged, and the seeded archive
(plan 031) lacked releases Google still serves. Each release is replayed as a
commit on top of the current history, oldest first:

- ``--recovered SHA`` takes a bot commit from the force-pushed PR branch (still
  fetchable from GitHub by SHA, ``git fetch origin <sha>``). Its CSV blob is
  used as is, its ledger's last row supplies the release and the date the job
  collected it, and its author date is kept, so the commit records when the
  release was really caught.
- ``--download RELEASE`` fetches ``geotargets-RELEASE.csv.zip`` from Google's
  dated static URL through the module's own download and header check, and
  records today's UTC date in ``date_collected``.

Each commit writes the release's CSV and the final ledger cut at that release,
so the ledger reads in release order at every step. A last commit restores the
CSV the history started from, with the full ledger, so the tip is the newest
release again. ``git log`` is not chronological across the backfill, but
``git log -- data/locations/geotargets.csv`` holds every snapshot.

Run from the repo root on a clean tree:

    uv run python .planners/plans/065-keep-every-geotargets-release/backfill_history.py \
        --recovered <sha> --download 2026-01-22 ...
"""

import argparse
import csv
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from WebSearcher.locations import check_geotargets_header, download_csv, release_date

GEOTARGETS_FP = Path("data/locations/geotargets.csv")
LEDGER_FP = Path("data/locations/ledger.csv")
DATED_URL = "https://developers.google.com/static/google-ads/api/data/geo/geotargets-{}.csv.zip"


def git_bytes(*args: str, env: dict[str, str] | None = None) -> bytes:
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(["git", *args], check=True, capture_output=True, env=full_env).stdout


def git(*args: str, env: dict[str, str] | None = None) -> str:
    return git_bytes(*args, env=env).decode("utf-8")


def read_ledger_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(text.splitlines()))


def write_ledger(rows: list[dict[str, str]]) -> None:
    with open(LEDGER_FP, "w", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["date_collected", "filename"])
        writer.writerows([row["date_collected"], row["filename"]] for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovered", action="append", default=[], metavar="SHA")
    parser.add_argument("--download", action="append", default=[], metavar="RELEASE")
    args = parser.parse_args()

    if git("status", "--porcelain", "--", str(GEOTARGETS_FP), str(LEDGER_FP)):
        raise SystemExit("locations files have uncommitted changes")
    start_sha = git("rev-parse", "HEAD").strip()
    start_csv = git_bytes("show", f"{start_sha}:{GEOTARGETS_FP}")
    ledger = read_ledger_rows(LEDGER_FP.read_text(encoding="utf-8"))
    tip_filename = ledger[-1]["filename"]
    have = {release_date(row["filename"]) for row in ledger}

    # (release date, ledger row, CSV source, author date or None)
    backfill = []
    for sha in args.recovered:
        row = read_ledger_rows(git("show", f"{sha}:{LEDGER_FP}"))[-1]
        author_date = git("log", "-1", "--format=%aI", sha).strip()
        backfill.append((release_date(row["filename"]), row, ("blob", sha), author_date))
    today = datetime.now(UTC).date().isoformat()
    for release in args.download:
        row = {"date_collected": today, "filename": f"geotargets-{release}.csv"}
        backfill.append((release, row, ("url", DATED_URL.format(release)), None))
    backfill.sort(key=lambda item: item[0])

    for release, _, _, _ in backfill:
        if release in have:
            raise SystemExit(f"already in the ledger: {release}")
        if release > release_date(tip_filename):
            raise SystemExit(f"newer than the ledger's tip: {release}")

    final = sorted(
        ledger + [row for _, row, _, _ in backfill], key=lambda r: release_date(r["filename"])
    )
    print(f"backfilling {len(backfill)} releases onto {start_sha[:7]}")

    for release, _, (kind, source), author_date in backfill:
        if kind == "blob":
            GEOTARGETS_FP.write_bytes(git_bytes("show", f"{source}:{GEOTARGETS_FP}"))
        else:
            download_csv(source, GEOTARGETS_FP)
        check_geotargets_header(GEOTARGETS_FP)
        write_ledger([row for row in final if release_date(row["filename"]) <= release])
        git("add", str(GEOTARGETS_FP), str(LEDGER_FP))
        env = {"GIT_AUTHOR_DATE": author_date} if author_date else None
        git("commit", "-m", f"update locations: geotargets-{release}", env=env)
        print(f"committed geotargets-{release} ({kind})")

    GEOTARGETS_FP.write_bytes(start_csv)
    write_ledger(final)
    git("add", str(GEOTARGETS_FP), str(LEDGER_FP))
    git("commit", "-m", f"update locations: {tip_filename.removesuffix('.csv')}")
    print(f"restored {tip_filename}")


if __name__ == "__main__":
    main()
