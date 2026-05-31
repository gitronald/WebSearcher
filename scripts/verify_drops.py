"""Pass B: confirm the 8 proposed fixture drops lose no parser coverage.

For each drop, we ask the strict question: is every bit of parser coverage it
exercises ALSO present in at least one SURVIVING record (the whole corpus minus all 8
drops)? Coverage is measured at four granularities:

  * component   = (type, sub_type)
  * detail_shape= (type, sub_type, sorted(details.keys()), details.get("type"))
  * error       = (type, sub_type, error)
  * fields      = (type, sub_type, which of title/url/text/cite are non-null)

`drop_only` = coverage tuples present in the drop but in NO survivor. A non-empty
drop_only is a rescue flag.

Usage:
    uv run python scripts/verify_drops.py            # coverage diff for all 8
    uv run python scripts/verify_drops.py --dump ID  # readable results+details dump
"""

import argparse
import bz2
from pathlib import Path

import orjson

import WebSearcher as ws

FIXTURES_DIR = Path("tests/fixtures")

# drop -> the record whose distinct-type signature preserves it (for reference only;
# the coverage test below is against the WHOLE surviving corpus, not just this one).
DROPS = {
    "97404b7b7c61": "7049404a2dd6",
    "45b6e019bfa2": "7049404a2dd6",
    "c9ab650f5bda": "7049404a2dd6",
    "032572e185d3": "7049404a2dd6",
    "be99c971b8f7": "7049404a2dd6",
    "cad43c3268a8": "9ed1baa7715d",
    "3c09a0f0c92f": "f006c9318116",
    "984065877aad": "9a7e39d95bf0",
}


def load_all() -> dict[str, dict]:
    recs = {}
    for p in sorted(FIXTURES_DIR.glob("*.json.bz2")):
        with bz2.open(p, "rt") as f:
            for line in f:
                r = orjson.loads(line)
                recs[r["serp_id"][:12]] = r
    return recs


def coverage(parsed: dict) -> dict[str, set]:
    comp, shape, err, fields = set(), set(), set(), set()
    for r in parsed["results"]:
        ts = (r["type"], r["sub_type"])
        comp.add(ts)
        d = r.get("details")
        if isinstance(d, dict):
            shape.add((ts, tuple(sorted(d.keys())), d.get("type")))
        elif isinstance(d, list):
            shape.add((ts, ("<list>",), None))
        if r.get("error") is not None:
            err.add((ts, r["error"]))
        present = tuple(k for k in ("title", "url", "text", "cite") if r.get(k) is not None)
        fields.add((ts, present))
    return {"component": comp, "detail_shape": shape, "error": err, "fields": fields}


def dump(rec: dict) -> None:
    parsed = ws.parse_serp(rec["html"])
    print(f"# {rec['serp_id'][:12]}  qry={rec.get('qry')!r}  v{rec.get('version')}")
    print(
        f"# {len(parsed['results'])} results / features.main_layout={parsed['features'].get('main_layout')}\n"
    )
    for r in parsed["results"]:
        print(
            f"[{r['cmpt_rank']}.{r['sub_rank']}] {r['type']}/{r['sub_type']}  "
            f"title={r['title']!r} url={(r['url'] or '')[:60]!r} err={r['error']!r}"
        )
        d = r.get("details")
        if d:
            print(f"      details={orjson.dumps(d).decode()[:400]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", metavar="ID")
    args = ap.parse_args()

    recs = load_all()

    if args.dump:
        dump(recs[args.dump])
        return

    # Surviving corpus = everything except the 8 drops.
    survivor_ids = [s for s in recs if s not in DROPS]
    survivor_cov = {"component": set(), "detail_shape": set(), "error": set(), "fields": set()}
    for s in survivor_ids:
        c = coverage(ws.parse_serp(recs[s]["html"]))
        for k in survivor_cov:
            survivor_cov[k] |= c[k]

    print(f"Survivors: {len(survivor_ids)} records.  Checking {len(DROPS)} drops.\n")
    all_clear = True
    for drop, preserver in DROPS.items():
        c = coverage(ws.parse_serp(recs[drop]["html"]))
        drop_only = {k: sorted(map(str, c[k] - survivor_cov[k])) for k in c}
        n_only = sum(len(v) for v in drop_only.values())
        status = "SAFE" if n_only == 0 else f"RESCUE ({n_only} drop-only)"
        if n_only:
            all_clear = False
        print(f"{drop}  {recs[drop].get('qry')[:38]!r:40s} -> survives via {preserver}: {status}")
        for k, v in drop_only.items():
            if v:
                print(f"    drop-only {k}:")
                for item in v:
                    print(f"      {item}")
    print(
        f"\n{'ALL 8 SAFE — no coverage lost vs surviving corpus.' if all_clear else 'RESCUES NEEDED — see above.'}"
    )


if __name__ == "__main__":
    main()
