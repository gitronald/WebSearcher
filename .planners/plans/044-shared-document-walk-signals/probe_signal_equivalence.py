"""Plan 044 equivalence gate: SignalIndex slices == per-subtree css('*') walks.

Monkeypatches SignalIndex.signals_for to compute the signals BOTH ways at the
same instant for every component classified across the corpus, asserting the
three sets are identical. Zero diffs required.
"""

import bz2
from pathlib import Path

import orjson

import WebSearcher as ws
import WebSearcher.classifiers.main as M

FIXTURE = Path("tests/fixtures/serps.json.bz2")

orig_signals_for = M.SignalIndex.signals_for
stats = {"checked": 0, "fallback": 0, "diffs": 0}


def checked_signals_for(self, cmpt):
    new = orig_signals_for(self, cmpt)
    if self._positions.get(cmpt.mem_id) is None:
        stats["fallback"] += 1
        return new
    old = M._ComponentSignals(cmpt.css("*"))
    stats["checked"] += 1
    if not (new.classes == old.classes and new.ids == old.ids and new.names == old.names):
        stats["diffs"] += 1
        print("DIFF:")
        print(
            "  classes new-old:", new.classes - old.classes, "old-new:", old.classes - new.classes
        )
        print("  ids new-old:", new.ids - old.ids, "old-new:", old.ids - new.ids)
        print("  names new-old:", new.names - old.names, "old-new:", old.names - new.names)
    return new


M.SignalIndex.signals_for = checked_signals_for

with bz2.open(FIXTURE, "rt") as f:
    records = [orjson.loads(line) for line in f]

for rec in records:
    ws.parse_serp(rec["html"])

print(
    f"components checked: {stats['checked']}, fallback-path: {stats['fallback']}, diffs: {stats['diffs']}"
)
assert stats["diffs"] == 0, "signal sets diverged"
print("EQUIVALENCE: PASS")
