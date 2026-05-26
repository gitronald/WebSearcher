"""Trace the growth of WebSearcher's component parsers over time.

Counts parser modules in WebSearcher/component_parsers/ at every commit that
touched that directory (excluding __init__.py and private _*.py helpers), then
plots the running count against commit date as a step chart. Every day a parser
is added or removed gets a faint guide line — rising for additions, dropping for
removals — ending in a horizontal label naming the type(s) that changed. Labels
are packed into stacked lanes (so guide lines vary in length) to keep them
readable and non-overlapping without scattering them away from their true date.

Run from anywhere: writes component_growth.png next to this script.
"""

import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PARSER_DIR = "WebSearcher/component_parsers"

STEP_COLOR = "#2c7fb8"
ADD_COLOR = "#1a7a34"
REMOVE_COLOR = "#c0392b"
GUIDE_COLOR = "#9aa0a6"

FONTSIZE = 12
LIST_FONTSIZE = 13  # the launch-parser column list
YMAX = 40  # hard top of the y-axis
ADD_RAIL = 39.5  # data-y of the top addition row; rows stack downward from here
TOP_GAP = 1.2  # tighter gap for the top two rows so both sit just above the line
TOP_BUMP = 0.8  # extra lift for the recent cluster's top pair (locations/short_videos)
LINE_GAP = 2.5  # earlier labels drop until their lowest row sits this far above the line
REMOVE_RAIL = 21  # data-y where the highest removal row sits (just under the line)
LANE_UNIT = 2.2  # vertical spacing per text row in the addition band (data-y)
REMOVE_STEP = 4  # vertical spacing between removal rows (data-y units)
XEND = datetime(2027, 1, 1)  # fixed right end of the x-axis
SHIFT_AFTER = datetime(2026, 1, 1)  # labels past this date nudge right of the steep climb
SHIFT_DAYS = 45  # how far to nudge them, so text clears the line


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def module_set(commit: str) -> set:
    tree = git("ls-tree", "--name-only", f"{commit}:{PARSER_DIR}")
    files = [f for f in tree.splitlines() if f.endswith(".py")]
    return {f[:-3] for f in files if f != "__init__.py" and not f.startswith("_")}


# Walk every commit that touched the parser dir, oldest first. Track the running
# count for the staircase, and roll up which types were added/removed per day.
commits = git("log", "--reverse", "--format=%H%x09%cI", "--", PARSER_DIR).splitlines()

dates, counts = [], []
day_adds = defaultdict(lambda: {"names": set(), "level": 0})
day_removes = defaultdict(lambda: {"names": set(), "level": 0})
prev: set = set()
for i, line in enumerate(commits):
    sha, iso = line.split("\t")
    cur = module_set(sha)
    if cur == prev:
        continue
    d = datetime.fromisoformat(iso)
    n = len(cur)
    dates.append(d)
    counts.append(n)
    if i == 0:  # initial commit seeds the catalog; list it separately below
        launch_names = sorted(cur)
        prev = cur
        continue
    day = d.date()
    for name in cur - prev:
        day_adds[day]["names"].add(name)
        day_adds[day]["level"] = n
    for name in prev - cur:
        day_removes[day]["names"].add(name)
        day_removes[day]["level"] = n
    prev = cur

# Extend the final level to "now" so the last step is visible
dates.append(datetime.now(dates[-1].tzinfo))
counts.append(counts[-1])


def build_labels(by_day: dict) -> list:
    """One label per parser. Parsers added on the same day share an x and the
    packer stacks them into their own rows, so every line gets full row spacing
    instead of being crammed together inside a multi-line block."""
    out = []
    for day in sorted(by_day):
        x = mdates.date2num(datetime(day.year, day.month, day.day))
        lvl = by_day[day]["level"]
        for name in sorted(by_day[day]["names"], key=lambda s: (len(s), s)):
            out.append({"x": x, "level": lvl, "text": name})
    return out


add_labels = build_labels(day_adds)
rem_labels = build_labels(day_removes)

fig, ax = plt.subplots(figsize=(20, 10))

# Staircase
ax.step(dates, counts, where="post", color=STEP_COLOR, linewidth=2.2, zorder=3)
ax.fill_between(dates, counts, step="post", alpha=0.15, color=STEP_COLOR, zorder=1)

# Lock the axes before measuring text, so widths come out in data x. The y-axis
# is capped at YMAX; addition labels are drawn above it (unclipped) and the saved
# figure expands to include them.
ax.set_ylim(0, YMAX)
ax.set_xlim(mdates.date2num(dates[0]), mdates.date2num(XEND))
fig.canvas.draw()
renderer = fig.canvas.get_renderer()
inv = ax.transData.inverted()


def text_width_days(label: str, fontsize: int = FONTSIZE) -> float:
    t = ax.text(0, 0, label, fontsize=fontsize, ha="left", va="bottom", linespacing=1.0)
    bb = t.get_window_extent(renderer=renderer)
    t.remove()
    (x0, _), (x1, _) = inv.transform([(0, 0), (bb.width, 0)])
    return x1 - x0


pad = text_width_days("nn")  # ~2-char gap between labels sharing a row


def pack_lanes(labels: list) -> None:
    """Height-aware interval packing: a multi-line label occupies as many rows
    as it has lines, so single-line labels can sit tightly between them."""
    row_right = []  # right edge (data x) currently occupied in each row
    for lab in sorted(labels, key=lambda d: d["x"]):
        w = text_width_days(lab["text"])
        h = lab["text"].count("\n") + 1
        r = 0
        while True:  # lowest start row whose next h rows are all free at this x
            free = all(
                rr >= len(row_right) or lab["x"] >= row_right[rr] + pad for rr in range(r, r + h)
            )
            if free:
                break
            r += 1
        for rr in range(r, r + h):
            while rr >= len(row_right):
                row_right.append(-1e9)
            row_right[rr] = lab["x"] + w
        lab["row"], lab["h"], lab["w"] = r, h, w


pack_lanes(add_labels)
pack_lanes(rem_labels)

rows = max(d["row"] + d["h"] for d in add_labels)  # tallest stack, for the title

# Group the earlier (pre-2026) labels into clusters of overlapping x-intervals and
# give each cluster ONE ceiling. Rows then step down by LANE_UNIT within a cluster
# (clean separation, no overlaps), while the whole stack still drops as close to
# the line as its depth and the line height allow.
shift_after = mdates.date2num(SHIFT_AFTER)
clusters, cluster_right = [], None
for lab in sorted((d for d in add_labels if d["x"] < shift_after), key=lambda d: d["x"]):
    if clusters and lab["x"] <= cluster_right + pad:
        clusters[-1].append(lab)
        cluster_right = max(cluster_right, lab["x"] + lab["w"])
    else:
        clusters.append([lab])
        cluster_right = lab["x"] + lab["w"]
for group in clusters:
    depth = max(d["row"] + 1 for d in group)
    top_level = max(d["level"] for d in group)
    ceiling = min(ADD_RAIL, top_level + LINE_GAP + (depth - 1) * LANE_UNIT)
    for d in group:
        d["ceiling"] = ceiling

# Draw additions: labels hang down from just under the top line, guides to curve.
# Recent labels are nudged right of the steep 2026 climb (with an elbow leader)
# so the text doesn't sit on top of the line.
for lab in add_labels:
    r = lab["row"]
    shifted = lab["x"] >= shift_after
    if shifted:
        # Recent cluster hangs from just under the cap; the top pair
        # (locations/short_videos) gets an extra lift to sit above the line's end.
        y = ADD_RAIL - (TOP_GAP + (r - 1) * LANE_UNIT if r else 0)
        if r <= 1:
            y += TOP_BUMP
        tx = lab["x"] + SHIFT_DAYS
    else:
        # Earlier labels hang from their cluster's shared ceiling: short clusters
        # over a low line drop far; tall clusters or a high line stay near the rail.
        y = lab["ceiling"] - r * LANE_UNIT
        tx = lab["x"]
    ax.plot(
        [lab["x"], lab["x"]],
        [lab["level"], y],
        color=GUIDE_COLOR,
        lw=1.0,
        ls=":",
        alpha=0.55,
        zorder=2,
    )
    if tx != lab["x"]:
        ax.plot(
            [lab["x"], tx],
            [y, y],
            color=GUIDE_COLOR,
            lw=1.0,
            ls=":",
            alpha=0.55,
            zorder=2,
            clip_on=False,
        )
    ax.plot(lab["x"], lab["level"], "o", ms=3.5, color=STEP_COLOR, zorder=3)
    # clip_on=False so a long name near the right edge (e.g. most_read_articles)
    # isn't cut off; the tight-bbox save keeps it while the axis still ends at 2027
    ax.text(
        tx,
        y,
        lab["text"],
        ha="left",
        va="top",
        fontsize=FONTSIZE,
        color=ADD_COLOR,
        linespacing=1.0,
        zorder=4,
        clip_on=False,
    )

# Draw removals (guides drop from the curve into the empty space beneath it)
for lab in rem_labels:
    y = REMOVE_RAIL - lab["row"] * REMOVE_STEP
    ax.plot(
        [lab["x"], lab["x"]],
        [lab["level"], y],
        color=GUIDE_COLOR,
        lw=1.0,
        ls=":",
        alpha=0.55,
        zorder=2,
    )
    ax.plot(lab["x"], lab["level"], "o", ms=3.5, color=STEP_COLOR, zorder=3)
    ax.text(
        lab["x"],
        y,
        lab["text"],
        ha="left",
        va="bottom",
        fontsize=FONTSIZE,
        color=REMOVE_COLOR,
        linespacing=1.0,
        zorder=4,
    )

# The 16 founding parsers, listed in columns in the empty space under the curve
ax.text(
    mdates.date2num(dates[0]) + 30,
    counts[0] - 1.5,
    f"{counts[0]} parsers at launch:",
    fontsize=FONTSIZE,
    color=STEP_COLOR,
    va="top",
    style="italic",
)
ncols, nrows = 4, 4
col_w = max(text_width_days(n, LIST_FONTSIZE) for n in launch_names) + text_width_days(
    "nn", LIST_FONTSIZE
)
x0 = mdates.date2num(dates[0]) + 30
for c in range(ncols):
    chunk = launch_names[c * nrows : (c + 1) * nrows]
    ax.text(
        x0 + c * col_w,
        counts[0] - 4,
        "\n".join(chunk),
        fontsize=LIST_FONTSIZE,
        color=STEP_COLOR,
        va="top",
        ha="left",
        linespacing=1.4,
        zorder=4,
    )

ax.set_title("WebSearcher component parsers over time", fontsize=15, pad=12)
ax.set_xlabel("Date")
ax.set_ylabel("Component parser modules")
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.set_yticks(range(0, 41, 5))
ax.axhline(0, color="#cccccc", lw=0.8, zorder=1)
ax.grid(axis="y", alpha=0.3)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
fig.savefig(HERE / "component_growth.png", dpi=150, bbox_inches="tight")

print(f"{len(counts) - 2} change-points; {counts[0]} -> {counts[-1]} modules")
print(f"{len(add_labels)} addition days ({rows} rows), {len(rem_labels)} removal days")
