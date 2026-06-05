"""Report SERP signature redundancy across the consolidated corpus.

Reads tests/fixtures/serps.json.bz2 and, for every record, builds the components in
SERP order (one entry per cmpt_rank, from its sub_rank==0 row) under three readings:

    sig_type     = "knowledge > general > general > people_also_ask > ..."   (incl. repeats)
    sig_full     = "knowledge[panel] > general > ..."                        (incl. sub_type)
    sig_distinct = "knowledge > general > people_also_ask > ..."             (repeats collapsed)

It then surfaces *clusters* of records that share a distinct-type signature -- i.e.
records whose component sequence is structurally similar -- as candidates a human
might review for redundancy.

IMPORTANT: this is a REPORT, not a drop recommender. A shared (type, sub_type)
signature does NOT prove two records are interchangeable: the signature is blind to
details-level structure. For example, two `ai_overview/sectioned` records can differ
in section COUNT (1 vs 3 sections), and a query-keyed test may depend on the
multi-section one specifically (see test_ai_overview_legacy_sge.py). Always confirm
at the details level (and check the query-keyed tests) before removing anything.

Usage:
    uv run python scripts/compare_drop_signatures.py
"""

from collections import Counter, defaultdict

from _common import load_serp_records

import WebSearcher as ws


def ordered_components(parsed: dict) -> list[tuple[str, str | None]]:
    by_cmpt: dict[int, dict] = {}
    for r in parsed["results"]:
        c = r["cmpt_rank"]
        if c not in by_cmpt or r["sub_rank"] < by_cmpt[c]["sub_rank"]:
            by_cmpt[c] = r
    return [(by_cmpt[c]["type"], by_cmpt[c]["sub_type"]) for c in sorted(by_cmpt)]


def sig_type(comps) -> str:
    return " > ".join(t for t, _ in comps)


def sig_full(comps) -> str:
    return " > ".join(f"{t}[{s}]" if s else t for t, s in comps)


def sig_distinct(comps) -> str:
    seen, out = set(), []
    for t, _ in comps:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return " > ".join(out)


def main() -> None:
    prof = {}
    for r in load_serp_records():
        comps = ordered_components(ws.parse_serp(r["html"]))
        prof[r["serp_id"][:12]] = {
            "short": r["serp_id"][:12],
            "qry": r.get("qry", ""),
            "rich_types": {t for t, _ in comps if t != "general"},
            "sig_type": sig_type(comps),
            "sig_full": sig_full(comps),
            "sig_distinct": sig_distinct(comps),
        }

    type_freq = Counter(p["sig_type"] for p in prof.values())
    full_freq = Counter(p["sig_full"] for p in prof.values())
    distinct_freq = Counter(p["sig_distinct"] for p in prof.values())

    print(f"Corpus: {len(prof)} records.\n")
    print("Signature uniqueness across the corpus (3 readings):")
    print(
        f"  ordered incl. repeats (type):        {sum(1 for p in prof.values() if type_freq[p['sig_type']] == 1)}/{len(prof)} unique"
    )
    print(
        f"  ordered incl. repeats + sub_type:    {sum(1 for p in prof.values() if full_freq[p['sig_full']] == 1)}/{len(prof)} unique"
    )
    print(
        f"  distinct types, order, no repeats:   {sum(1 for p in prof.values() if distinct_freq[p['sig_distinct']] == 1)}/{len(prof)} unique\n"
    )

    clusters = defaultdict(list)
    for p in prof.values():
        clusters[p["sig_distinct"]].append(p)
    shared = {sig: members for sig, members in clusters.items() if len(members) > 1}

    print("=" * 100)
    print(
        f"DISTINCT-TYPE SIGNATURE CLUSTERS (>=2 records share a component sequence): {len(shared)}"
    )
    print("REVIEW ONLY -- confirm details-level structure + query-keyed tests before removing any.")
    print("('general' = plain organic results, on nearly every SERP, so it carries no")
    print(" signal; the line below names only the specialized component types in the")
    print(" shared sequence -- the distinctive parser paths worth comparing.)")
    print("=" * 100)
    for sig, members in sorted(shared.items(), key=lambda kv: -len(kv[1])):
        specialized = sorted({rt for m in members for rt in m["rich_types"]})
        print(f"\n[{len(members)} records]  {sig}")
        print(f"  specialized (non-'general') component types: {specialized or '(none)'}")
        for m in members:
            print(f"    {m['short']}  {m['qry'][:60]!r}")


if __name__ == "__main__":
    main()
