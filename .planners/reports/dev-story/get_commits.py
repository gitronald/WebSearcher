"""Grab every commit from the WebSearcher repo into a CSV.

Columns: commit (full hash), timestamp (committer date, ISO 8601), message
(subject line). Uses a unit-separator delimiter and Python's csv module so
commas/quotes in messages stay inside their column.

Run from anywhere: writes commits.csv next to this script.
"""

import csv
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]  # .planners/reports/dev-story -> repo root
SEP = "\x1f"  # unit separator, unlikely to appear in commit data

out = subprocess.run(
    ["git", "-C", str(REPO), "log", f"--pretty=format:%H{SEP}%cI{SEP}%s"],
    capture_output=True,
    text=True,
    check=True,
)

rows = [line.split(SEP, 2) for line in out.stdout.splitlines()]
with open(HERE / "commits.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["commit", "timestamp", "message"])
    writer.writerows(rows)

print(f"wrote commits.csv ({len(rows)} commits)")
