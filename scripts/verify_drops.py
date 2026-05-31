"""Verify the consolidated SERP corpus integrity (post plan-032).

Confirms the plan-032 pruning + consolidation landed cleanly in
tests/fixtures/serps.json.bz2:

  * the 8 dropped records are absent
  * serp_ids are unique
  * every record carries a non-empty `note`
  * the three witnessed layouts are still present (standard / standard-overview /
    standard-airfares) -- the set test_features_expose_main_layout pins
  * every (type, sub_type) pair the corpus parses has at least one carrier (sanity)

Exits non-zero if any check fails, so it can double as a CI guard.

Usage:
    uv run python scripts/verify_drops.py
    uv run python scripts/verify_drops.py --dump ID   # readable results+details dump
"""

import argparse
import bz2
import sys
from collections import Counter
from pathlib import Path

import orjson

import WebSearcher as ws

FIXTURE = Path("tests/fixtures") / "serps.json.bz2"

# The 8 records removed by plan 032 (must no longer be present).
PLAN032_DROPS = {
    "97404b7b7c61",
    "45b6e019bfa2",
    "c9ab650f5bda",
    "032572e185d3",
    "be99c971b8f7",
    "cad43c3268a8",
    "3c09a0f0c92f",
    "984065877aad",
}
REQUIRED_LAYOUTS = {"standard", "standard-overview", "standard-airfares"}


def load() -> list[dict]:
    with bz2.open(FIXTURE, "rt") as f:
        return [orjson.loads(line) for line in f]


def dump(rec: dict) -> None:
    parsed = ws.parse_serp(rec["html"])
    print(f"# {rec['serp_id'][:12]}  qry={rec.get('qry')!r}  v{rec.get('version')}")
    print(
        f"# {len(parsed['results'])} results / main_layout={parsed['features'].get('main_layout')}\n"
    )
    for r in parsed["results"]:
        print(
            f"[{r['cmpt_rank']}.{r['sub_rank']}] {r['type']}/{r['sub_type']}  "
            f"title={r['title']!r} url={(r['url'] or '')[:60]!r} err={r['error']!r}"
        )
        if r.get("details"):
            print(f"      details={orjson.dumps(r['details']).decode()[:400]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", metavar="ID")
    args = ap.parse_args()

    recs = load()
    by_id = {r["serp_id"][:12]: r for r in recs}

    if args.dump:
        dump(by_id[args.dump])
        return

    checks: list[tuple[str, bool, str]] = []

    present_drops = sorted(PLAN032_DROPS & set(by_id))
    checks.append(("8 plan-032 drops absent", not present_drops, f"still present: {present_drops}"))

    checks.append(
        (
            "serp_ids unique",
            len(by_id) == len(recs),
            f"{len(recs)} records, {len(by_id)} unique ids",
        )
    )

    no_note = [r["serp_id"][:12] for r in recs if not r.get("note")]
    checks.append(("every record has a note", not no_note, f"missing note: {no_note}"))

    layouts = Counter(ws.parse_serp(r["html"])["features"].get("main_layout") for r in recs)
    missing_layouts = REQUIRED_LAYOUTS - set(layouts)
    checks.append(("required layouts present", not missing_layouts, f"missing: {missing_layouts}"))

    pairs = Counter(
        (res["type"], res["sub_type"]) for r in recs for res in ws.parse_serp(r["html"])["results"]
    )
    checks.append(("every (type,sub_type) has a carrier", all(c > 0 for c in pairs.values()), ""))

    print(f"Corpus: {len(recs)} records, {len(pairs)} distinct (type,sub_type) pairs")
    print(f"layouts: {dict(layouts)}\n")
    ok = True
    for name, passed, detail in checks:
        ok &= passed
        mark = "PASS" if passed else "FAIL"
        print(f"  [{mark}] {name}" + (f"  -- {detail}" if not passed else ""))
    print(f"\n{'ALL CHECKS PASSED' if ok else 'INTEGRITY CHECK FAILED'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
