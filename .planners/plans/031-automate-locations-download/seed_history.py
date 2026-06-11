"""One-off: replay the geotargets snapshot archive into git history.

Walks a directory of bz2-compressed geotargets snapshots whose upstream
filenames were preserved as downloaded (both the ``geotargets-YYYY-MM-DD.csv``
shape and the older ``AdWords API Location Criteria YYYY-MM-DD.csv`` shape),
oldest release first, and for each one:

1. decompresses and normalizes it through the same csv round-trip the
   downloader uses (irons out the archive's mixed LF/CRLF line endings),
2. overwrites ``data/locations/geotargets.csv``,
3. appends a ledger row (``date_collected`` empty -- the original pull dates
   were never recorded),
4. commits as ``update locations: geotargets-YYYY-MM-DD``.

Run from the repo root of the checkout whose history is being seeded:

    uv run python .planners/plans/031-automate-locations-download/seed_history.py \
        --archive-dir <path-to-bz2-snapshot-dir>
"""

import argparse
import bz2
import re
import subprocess
from pathlib import Path

from WebSearcher.locations import append_ledger_row, normalize_csv_text, write_csv

RELEASE_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
GEOTARGETS_FP = Path("data/locations/geotargets.csv")
LEDGER_FP = Path("data/locations/ledger.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", required=True, type=Path)
    args = parser.parse_args()

    snapshots = []
    for snapshot_fp in args.archive_dir.glob("*.csv.bz2"):
        match = RELEASE_DATE.search(snapshot_fp.name)
        if not match:
            raise ValueError(f"no release date in filename: {snapshot_fp.name}")
        snapshots.append((match.group(0), snapshot_fp))
    snapshots.sort()
    print(f"replaying {len(snapshots)} snapshots")

    GEOTARGETS_FP.parent.mkdir(parents=True, exist_ok=True)
    for release_date, snapshot_fp in snapshots:
        text = bz2.decompress(snapshot_fp.read_bytes()).decode("utf-8")
        write_csv(str(GEOTARGETS_FP), normalize_csv_text(text))
        append_ledger_row(
            LEDGER_FP,
            date_collected="",
            filename=snapshot_fp.name.removesuffix(".bz2"),
        )
        subprocess.run(["git", "add", str(GEOTARGETS_FP), str(LEDGER_FP)], check=True)
        subprocess.run(
            ["git", "commit", "-m", f"update locations: geotargets-{release_date}"],
            check=True,
        )


if __name__ == "__main__":
    main()
