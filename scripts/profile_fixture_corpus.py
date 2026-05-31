"""Profile the bulk SERP fixture corpus to assess each record's unique contribution.

For every record in the bulk fixtures (the ones without a curated ``note``), this
parses the stored HTML and emits:

  * provenance (qry, version, timestamp, html size)
  * SERP features (main_layout + boolean/notice flags that fired)
  * the component signature: the set of (type, sub_type) pairs present
  * parse health: error strings, unclassified/unknown counts

Then it computes, corpus-wide, which (type, sub_type) pairs and which layouts are
*rare* (carried by only 1-2 records), and flags records whose entire signature is
a subset of some other single record -- i.e. structural near-duplicates that are
candidate drops.

Usage:
    uv run python scripts/profile_fixture_corpus.py
    uv run python scripts/profile_fixture_corpus.py --json > corpus_profile.json
"""

import argparse
import bz2
import json
from collections import Counter, defaultdict
from pathlib import Path

import orjson

import WebSearcher as ws

FIXTURES_DIR = Path("tests/fixtures")
# The consolidated corpus (plan 032). Falls back to the pre-consolidation bulk
# files if the single file is absent.
BULK_GLOBS = (
    ["serps.json.bz2"]
    if (FIXTURES_DIR / "serps.json.bz2").exists()
    else [
        "serps-v0.6.7.json.bz2",
        "serps-v0.6.8.json.bz2",
        "serps-parser-coverage.json.bz2",
        "serps-sge-2024.json.bz2",
    ]
)


def load(path: Path) -> list[dict]:
    with bz2.open(path, "rt") as f:
        return [orjson.loads(line) for line in f]


def profile_record(rec: dict) -> dict:
    parsed = ws.parse_serp(rec["html"])
    results = parsed["results"]
    features = parsed["features"]

    sig = sorted(
        {(r["type"], r["sub_type"]) for r in results},
        key=lambda ts: (ts[0] or "", ts[1] or ""),
    )
    type_counts = Counter(r["type"] for r in results)
    sub_type_counts = Counter((r["type"], r["sub_type"]) for r in results)
    errors = [r["error"] for r in results if r["error"] is not None]
    fired_flags = sorted(
        k for k, v in features.items() if isinstance(v, bool) and v and k != "captcha"
    )

    return {
        "serp_id": rec["serp_id"],
        "short_id": rec["serp_id"][:12],
        "qry": rec.get("qry", ""),
        "version": rec.get("version", ""),
        "timestamp": rec.get("timestamp", ""),
        "html_chars": len(rec["html"]),
        "main_layout": features.get("main_layout"),
        "language": features.get("language"),
        "fired_flags": fired_flags,
        "n_results": len(results),
        "n_components": len({r["cmpt_rank"] for r in results}),
        "types": dict(type_counts),
        "signature": [f"{t}/{s}" for t, s in sig],
        "sub_type_counts": {f"{t}/{s}": c for (t, s), c in sub_type_counts.items()},
        "n_errors": len(errors),
        "errors": dict(Counter(errors)),
        "n_unclassified": type_counts.get("unclassified", 0),
        "n_unknown": type_counts.get("unknown", 0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit full JSON profile")
    args = ap.parse_args()

    profiles: list[dict] = []
    source_of: dict[str, list[str]] = {}  # file -> [short_id]
    for name in BULK_GLOBS:
        path = FIXTURES_DIR / name
        if not path.exists():
            continue
        ids = []
        for rec in load(path):
            p = profile_record(rec)
            p["file"] = name
            profiles.append(p)
            ids.append(p["short_id"])
        source_of[name] = ids

    # Corpus-wide rarity: how many records carry each (type/sub_type) pair.
    pair_carriers: dict[str, set[str]] = defaultdict(set)
    layout_carriers: dict[str, set[str]] = defaultdict(set)
    for p in profiles:
        for pair in p["signature"]:
            pair_carriers[pair].add(p["short_id"])
        layout_carriers[str(p["main_layout"])].add(p["short_id"])

    # A record's "unique pairs" = signature pairs that no other record has.
    for p in profiles:
        unique = [pr for pr in p["signature"] if len(pair_carriers[pr]) == 1]
        rare = [pr for pr in p["signature"] if len(pair_carriers[pr]) == 2]
        p["unique_pairs"] = unique
        p["rare_pairs"] = rare
        p["sole_layout"] = len(layout_carriers[str(p["main_layout"])]) == 1

    # Subset detection: record A is a drop-candidate if its signature set is a
    # subset of some other record B's signature, AND A contributes no unique pair.
    sig_sets = {p["short_id"]: set(p["signature"]) for p in profiles}
    for p in profiles:
        a = sig_sets[p["short_id"]]
        supersets = [
            q["short_id"]
            for q in profiles
            if q["short_id"] != p["short_id"] and a < sig_sets[q["short_id"]]
        ]
        equals = [
            q["short_id"]
            for q in profiles
            if q["short_id"] != p["short_id"] and a == sig_sets[q["short_id"]]
        ]
        p["covered_by"] = supersets
        p["identical_signature_to"] = equals
        p["drop_candidate"] = (not p["unique_pairs"]) and bool(supersets or equals)

    if args.json:
        print(json.dumps(profiles, indent=2, default=str))
        return

    # Human-readable report -------------------------------------------------
    print(f"BULK CORPUS: {len(profiles)} records across {len(source_of)} files\n")
    total_chars = sum(p["html_chars"] for p in profiles)
    print(f"total HTML: {total_chars / 1e6:.1f} MB uncompressed\n")

    print("=" * 100)
    print("PER-RECORD PROFILE")
    print("=" * 100)
    for p in sorted(profiles, key=lambda x: (x["file"], -x["html_chars"])):
        flag = " [DROP?]" if p["drop_candidate"] else ""
        print(f"\n{p['short_id']}  {p['file']}{flag}")
        print(
            f"  qry: {p['qry']!r}  | v{p['version']} | {p['timestamp'][:10]} | {p['html_chars'] / 1e3:.0f}k chars"
        )
        print(f"  layout={p['main_layout']}  lang={p['language']}  flags={p['fired_flags']}")
        print(f"  {p['n_results']} results / {p['n_components']} components")
        print(f"  signature: {p['signature']}")
        if p["unique_pairs"]:
            print(f"  UNIQUE pairs (only this record): {p['unique_pairs']}")
        if p["rare_pairs"]:
            print(f"  rare pairs (2 records): {p['rare_pairs']}")
        if p["sole_layout"]:
            print(f"  SOLE record with layout={p['main_layout']}")
        if p["errors"]:
            print(f"  errors: {p['errors']}")
        if p["covered_by"]:
            print(f"  signature subset of: {p['covered_by']}")
        if p["identical_signature_to"]:
            print(f"  identical signature to: {p['identical_signature_to']}")

    print("\n" + "=" * 100)
    print("CORPUS-WIDE (type/sub_type) FREQUENCY  (carriers = how many records)")
    print("=" * 100)
    for pair, carriers in sorted(pair_carriers.items(), key=lambda kv: len(kv[1])):
        print(f"  {len(carriers):2d}  {pair}")

    print("\n" + "=" * 100)
    print("LAYOUT FREQUENCY")
    print("=" * 100)
    for layout, carriers in sorted(layout_carriers.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(carriers):2d}  {layout}")

    drops = [p for p in profiles if p["drop_candidate"]]
    print("\n" + "=" * 100)
    print(f"DROP CANDIDATES (no unique pair + signature covered elsewhere): {len(drops)}")
    print("=" * 100)
    for p in drops:
        tgt = p["covered_by"] or p["identical_signature_to"]
        print(f"  {p['short_id']}  {p['file']:38s} {p['qry']!r:40s} -> {tgt}")


if __name__ == "__main__":
    main()
