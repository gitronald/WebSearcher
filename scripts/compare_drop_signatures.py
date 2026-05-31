"""Compare drop-candidate SERPs under an ORDERED component-name signature.

The corpus profiler (`profile_fixture_corpus.py`) screens redundancy with an
*unordered set* of (type, sub_type) pairs and a subset test. This script applies a
stricter lens -- the user's definition of a "SERP signature": the components listed
**in SERP order**, concatenated into a string. Order and multiplicity both count, so
[general, general, knowledge] != [knowledge, general].

For every record we build, ordered by cmpt_rank (one entry per component, taken from
its sub_rank==0 row):

    sig_type  =  "knowledge > general > general > people_also_ask > ..."
    sig_full  =  "knowledge[panel] > general > general > people_also_ask > ..."

Then, for each drop candidate (snapshot-only files, set-subset of a keeper, no
unique pair, excluding the designated keepers), we report whether its ordered
signature is duplicated **anywhere else in the corpus** -- and show it side by side
with the keeper it was matched to, so redundancy can be eyeballed.

Usage:
    uv run python scripts/compare_drop_signatures.py
"""

import bz2
from collections import Counter, defaultdict
from pathlib import Path

import orjson

import WebSearcher as ws

FIXTURES_DIR = Path("tests/fixtures")

# Records kept by explicit decision despite a subset signature:
#   sky-blue representatives (keep 2) + the sole standard-overview in the snapshot set
KEEP_OVERRIDE = {"aa594f199c3d", "6aa70651b0cd", "f6fae1c9a96e"}

SNAPSHOT_FILES = {"serps-v0.6.7.json.bz2", "serps-v0.6.8.json.bz2"}


def load_all() -> list[dict]:
    out = []
    for p in sorted(FIXTURES_DIR.glob("*.json.bz2")):
        with bz2.open(p, "rt") as f:
            for line in f:
                r = orjson.loads(line)
                r["_file"] = p.name
                out.append(r)
    return out


def ordered_components(parsed: dict) -> list[tuple[str, str | None]]:
    """One (type, sub_type) per component, in cmpt_rank order (sub_rank==0 row)."""
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
    """Distinct component TYPES in first-appearance order (collapse repeats)."""
    seen, out = set(), []
    for t, _ in comps:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return " > ".join(out)


def diff_marks(a: str, b: str) -> str:
    """Human note comparing two ' > '-joined signatures."""
    A, B = a.split(" > "), b.split(" > ")
    if A == B:
        return "IDENTICAL ordered signature"
    ca, cb = Counter(A), Counter(B)
    only_a = list((ca - cb).elements())
    only_b = list((cb - ca).elements())
    parts = []
    if only_a:
        parts.append(f"candidate has extra: {only_a}")
    if only_b:
        parts.append(f"keeper has extra: {only_b}")
    if not parts:
        parts.append("same multiset, different ORDER")
    return "; ".join(parts)


def main() -> None:
    records = load_all()

    # Per-record profile
    prof = {}
    for r in records:
        parsed = ws.parse_serp(r["html"])
        comps = ordered_components(parsed)
        prof[r["serp_id"][:12]] = {
            "short": r["serp_id"][:12],
            "file": r["_file"],
            "qry": r.get("qry", ""),
            "comps": comps,
            "pair_set": {(t, s) for t, s in comps},
            "rich_types": {t for t, _ in comps if t != "general"},
            "sig_type": sig_type(comps),
            "sig_full": sig_full(comps),
            "sig_distinct": sig_distinct(comps),
            "n": len(comps),
        }

    # Corpus-wide ordered-signature frequency (across ALL files)
    type_freq = Counter(p["sig_type"] for p in prof.values())
    full_freq = Counter(p["sig_full"] for p in prof.values())
    distinct_freq = Counter(p["sig_distinct"] for p in prof.values())
    type_carriers = defaultdict(list)
    full_carriers = defaultdict(list)
    for p in prof.values():
        type_carriers[p["sig_type"]].append(p["short"])
        full_carriers[p["sig_full"]].append(p["short"])

    # Unique (type/sub_type) pairs -> keeper screen (matches the profiler)
    pair_carriers = defaultdict(set)
    for p in prof.values():
        for pair in p["pair_set"]:
            pair_carriers[pair].add(p["short"])

    # Drop candidates: snapshot-only, subset of another's pair_set, no unique pair,
    # not a designated keeper.
    sig_sets = {s: p["pair_set"] for s, p in prof.items()}
    drops = []
    for s, p in prof.items():
        if p["file"] not in SNAPSHOT_FILES or s in KEEP_OVERRIDE:
            continue
        if any(len(pair_carriers[pr]) == 1 for pr in p["pair_set"]):
            continue  # carries a unique pair -> keeper
        supersets = [q for q in prof if q != s and sig_sets[s] < sig_sets[q]]
        equals = [q for q in prof if q != s and sig_sets[s] == sig_sets[q]]
        if supersets or equals:
            p["match"] = supersets or equals
            drops.append(p)

    # Report --------------------------------------------------------------
    print(f"Corpus: {len(prof)} records.  Drop candidates (set-subset screen): {len(drops)}\n")

    uniq_type = [p for p in drops if type_freq[p["sig_type"]] == 1]
    uniq_full = [p for p in drops if full_freq[p["sig_full"]] == 1]
    uniq_dist = [p for p in drops if distinct_freq[p["sig_distinct"]] == 1]
    print("ANSWER TO 'do any drops have a UNIQUE serp signature?' (3 readings)\n")
    print(
        f"  A. ordered, every component incl. repeats (TYPE):        {len(uniq_type):2d}/{len(drops)} unique"
    )
    print(
        f"  B. ordered, incl. repeats + sub_type (TYPE[sub_type]):    {len(uniq_full):2d}/{len(drops)} unique"
    )
    print(
        f"  C. distinct types, first-appearance order (no repeats):  {len(uniq_dist):2d}/{len(drops)} unique"
    )
    print("  (a unique STRING is not unique parser COVERAGE -- see rich-component column)\n")

    print("=" * 100)
    print("COMPACT SUMMARY  (rich = non-'general' component types absent from matched keeper)")
    print("=" * 100)
    print(f"{'serp_id':13s} {'qry':34s} {'A':3s} {'B':3s} {'C':3s} rich-components-keeper-lacks")
    for p in sorted(drops, key=lambda x: (x["file"], x["qry"])):
        keeper = prof[p["match"][0]]
        rich_extra = sorted(p["rich_types"] - keeper["rich_types"])
        a = "U" if type_freq[p["sig_type"]] == 1 else f"x{type_freq[p['sig_type']]}"
        b = "U" if full_freq[p["sig_full"]] == 1 else f"x{full_freq[p['sig_full']]}"
        c = "U" if distinct_freq[p["sig_distinct"]] == 1 else f"x{distinct_freq[p['sig_distinct']]}"
        verdict = rich_extra if rich_extra else "(none -- only differs by general count/order)"
        print(f"{p['short']:13s} {p['qry'][:34]:34s} {a:3s} {b:3s} {c:3s} {verdict}")
    print()

    # -- Apply chosen bar: DISTINCT-TYPE ORDER -----------------------------
    # A candidate may be dropped only if its distinct-type ordered signature is
    # still carried by a SURVIVING record. Records with a unique sig_distinct are
    # protected; within a cluster sharing a sig_distinct that no non-candidate
    # carries, keep one representative (the fullest by component count).
    cand_ids = {p["short"] for p in drops}
    noncand_sigs = {p["sig_distinct"] for s, p in prof.items() if s not in cand_ids}
    final_drop, protected = [], []
    by_sig = defaultdict(list)
    for p in drops:
        by_sig[p["sig_distinct"]].append(p)
    for sig, members in by_sig.items():
        members.sort(key=lambda x: -x["n"])  # fullest first
        if distinct_freq[sig] == 1:
            protected.extend((m, "unique distinct-type signature") for m in members)
        elif sig in noncand_sigs:
            survivors = sorted(
                s for s, pp in prof.items() if pp["sig_distinct"] == sig and s not in cand_ids
            )
            final_drop.extend((m, survivors) for m in members)
        else:
            protected.append((members[0], "representative of shared signature"))
            final_drop.extend((m, [members[0]["short"]]) for m in members[1:])

    print("=" * 100)
    print(
        f"FINAL DROP LIST under DISTINCT-TYPE bar: {len(final_drop)} drop / {len(protected)} protected (of {len(drops)} candidates)"
    )
    print("=" * 100)
    print("DROP (distinct-type signature survives elsewhere):")
    for p, preserved in sorted(final_drop, key=lambda x: x[0]["qry"]):
        print(f"  {p['short']}  {p['qry'][:42]:42s}  preserved by: {preserved}")
    print("\nPROTECTED (kept despite set-subset screen):")
    for p, why in sorted(protected, key=lambda x: x[0]["qry"]):
        print(f"  {p['short']}  {p['qry'][:42]:42s}  {why}")
    print()

    print("=" * 100)
    print("PER DROP-CANDIDATE COMPARISON  (ordered signature vs matched keeper)")
    print("=" * 100)
    for p in sorted(drops, key=lambda x: (x["file"], x["qry"])):
        keeper = prof[p["match"][0]]
        utype = (
            "UNIQUE"
            if type_freq[p["sig_type"]] == 1
            else f"x{type_freq[p['sig_type']]} ({type_carriers[p['sig_type']]})"
        )
        print(
            f"\n{p['short']}  {p['file'].replace('serps-', '').replace('.json.bz2', '')}  {p['qry']!r}"
        )
        print(f"  ordered TYPE sig [{utype}]:")
        print(f"    {p['sig_type']}")
        print(f"  full  sig: {p['sig_full']}")
        print(f"  matched keeper {keeper['short']} {keeper['qry']!r}:")
        print(f"    {keeper['sig_type']}")
        print(f"  delta: {diff_marks(p['sig_full'], keeper['sig_full'])}")


if __name__ == "__main__":
    main()
