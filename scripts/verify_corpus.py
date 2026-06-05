"""Verify the consolidated SERP fixture corpus integrity.

A generic corpus-integrity guard over tests/fixtures/serps.json.bz2:

  * serp_ids are unique
  * every record carries a non-empty `note`
  * every record parses to a non-null `features.main_layout` (parser health)
  * every record yields at least one result (no empty parse)

Exits non-zero if any check fails, so it can double as a CI guard.

Usage:
    uv run python scripts/verify_corpus.py
    uv run python scripts/verify_corpus.py --dump ID   # readable results+details dump
"""

import argparse
import sys
from collections import Counter

import orjson
from _common import load_serp_records, serp_label

import WebSearcher as ws


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

    recs = load_serp_records()
    by_id = {r["serp_id"][:12]: r for r in recs}

    if args.dump:
        dump(by_id[args.dump])
        return

    parsed = [ws.parse_serp(r["html"]) for r in recs]
    layouts = Counter(p["features"].get("main_layout") for p in parsed)
    pairs = Counter((res["type"], res["sub_type"]) for p in parsed for res in p["results"])

    no_note = [r["serp_id"][:12] for r in recs if not r.get("note")]
    no_layout = [
        serp_label(r)
        for r, p in zip(recs, parsed, strict=True)
        if not p["features"].get("main_layout")
    ]
    empty = [serp_label(r) for r, p in zip(recs, parsed, strict=True) if not p["results"]]

    checks = [
        (
            "serp_ids unique",
            len(by_id) == len(recs),
            f"{len(recs)} records, {len(by_id)} unique ids",
        ),
        ("every record has a note", not no_note, f"missing note: {no_note}"),
        ("every record has a main_layout", not no_layout, f"null layout: {no_layout}"),
        ("every record yields results", not empty, f"empty parse: {empty}"),
    ]

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
