"""Plot WebSearcher commit activity over time in 3-month (quarterly) bins.

Reads commits.csv next to this script, writes commit_activity.png next to it.
"""

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent

# Count commits per quarter (3-month bins)
counts = Counter()
with open(HERE / "commits.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        ts = datetime.fromisoformat(row["timestamp"])
        q_month = ((ts.month - 1) // 3) * 3 + 1
        counts[datetime(ts.year, q_month, 1)] += 1

quarters = sorted(counts)
values = [counts[q] for q in quarters]

fig, ax = plt.subplots(figsize=(12, 5))
ax.bar(quarters, values, width=70, color="#2c7fb8")
ax.set_title("WebSearcher commit activity over time (3-month bins)")
ax.set_xlabel("Quarter")
ax.set_ylabel("Commits")
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.xaxis.set_minor_locator(mdates.MonthLocator((1, 4, 7, 10)))
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(HERE / "commit_activity.png", dpi=150)
print(f"wrote commit_activity.png ({len(quarters)} quarters, {sum(values)} commits)")
