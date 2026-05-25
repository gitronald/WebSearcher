"""Trace the growth of WebSearcher's component parsers over time.

Counts parser modules in WebSearcher/component_parsers/ at every commit that
touched that directory (excluding __init__.py and private _*.py helpers), then
plots the running count against commit date as a step chart.

Run from anywhere: writes component_growth.png next to this script.
"""

import subprocess
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PARSER_DIR = "WebSearcher/component_parsers"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def module_count(commit: str) -> int:
    tree = git("ls-tree", "--name-only", f"{commit}:{PARSER_DIR}")
    files = [f for f in tree.splitlines() if f.endswith(".py")]
    return len([f for f in files if f != "__init__.py" and not f.startswith("_")])


# Commits that touched the parser dir, oldest first
commits = git("log", "--reverse", "--format=%H%x09%cI", "--", PARSER_DIR).splitlines()

dates, counts = [], []
for line in commits:
    sha, iso = line.split("\t")
    n = module_count(sha)
    d = datetime.fromisoformat(iso)
    # Keep only points where the count changed (dedupe flat stretches)
    if not counts or n != counts[-1]:
        dates.append(d)
        counts.append(n)

# Extend the final level to "now" so the last step is visible
dates.append(datetime.now(dates[-1].tzinfo))
counts.append(counts[-1])

fig, ax = plt.subplots(figsize=(12, 5))
ax.step(dates, counts, where="post", color="#2c7fb8", linewidth=2)
ax.fill_between(dates, counts, step="post", alpha=0.15, color="#2c7fb8")
ax.set_title("WebSearcher component parsers over time")
ax.set_xlabel("Date")
ax.set_ylabel("Component parser modules")
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.grid(axis="y", alpha=0.3)
ax.set_ylim(0, max(counts) + 3)
fig.tight_layout()
fig.savefig(HERE / "component_growth.png", dpi=150)

print(f"{len(counts) - 1} change-points; {counts[0]} -> {counts[-1]} modules")
print("\nmilestones:")
for d, c in zip(dates, counts):
    print(f"  {d:%Y-%m-%d}  {c}")
