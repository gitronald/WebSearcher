"""Build the consolidated SERP fixture corpus: tests/fixtures/serps.json.bz2.

Merges the seven version-named bz2 fixtures into one, dropping the 8 verified-
redundant records (plan 032), scrubbing private-repo names from notes, and adding a
`note` to every survivor. Notes are generated from the POST-DROP corpus so "sole
carrier" claims are accurate; curated notes are preserved (only scrubbed). The one
surviving google_abuse exemption token is kept intact as a deliberate artifact. The
HTML field is written last on each line for readability.

Usage:
    uv run python scripts/build_fixture_corpus.py            # write the file
    uv run python scripts/build_fixture_corpus.py --check    # report, do not write
"""

import argparse
import bz2
from collections import Counter, defaultdict
from pathlib import Path

import orjson

import WebSearcher as ws

FIXTURES_DIR = Path("tests/fixtures")
OUT = FIXTURES_DIR / "serps.json.bz2"

# Input files in the order they should appear in the consolidated file.
SOURCES = [
    "serps-parser-coverage.json.bz2",
    "serps-sge-2024.json.bz2",
    "serps-v0.6.7.json.bz2",
    "serps-v0.6.8.json.bz2",
    "serps-v0.7.2-ads.json.bz2",
    "serps-v0.7.2-jobs.json.bz2",
    "serps-v0.7.2-knowledge-subcards.json.bz2",
]

DROPS = {
    "97404b7b7c61",
    "45b6e019bfa2",
    "c9ab650f5bda",
    "032572e185d3",
    "be99c971b8f7",
    "cad43c3268a8",
    "3c09a0f0c92f",
    "984065877aad",
}

UBIQUITOUS = ("general/", "searches_related/", "people_also_ask/")


def scrub_note(note: str) -> str:
    return note.replace("SearchAudits directives crawl", "a directives crawl")


def signature(parsed: dict) -> list[str]:
    pairs = sorted(
        {(r["type"], r["sub_type"]) for r in parsed["results"]},
        key=lambda ts: (ts[0] or "", ts[1] or ""),
    )
    return [f"{t}/{s}" for t, s in pairs]


def load_sources() -> list[dict]:
    survivors = []
    for name in SOURCES:
        path = FIXTURES_DIR / name
        with bz2.open(path, "rt") as f:
            for line in f:
                r = orjson.loads(line)
                if r["serp_id"][:12] in DROPS:
                    continue
                r["_parsed"] = ws.parse_serp(r["html"])
                r["_sig"] = signature(r["_parsed"])
                r["_layout"] = r["_parsed"]["features"].get("main_layout")
                survivors.append(r)
    return survivors


def build_notes(survivors: list[dict]) -> None:
    pair_carriers: dict[str, set] = defaultdict(set)
    layout_carriers: dict[str, set] = defaultdict(set)
    for r in survivors:
        sid = r["serp_id"][:12]
        for p in r["_sig"]:
            pair_carriers[p].add(sid)
        layout_carriers[str(r["_layout"])].add(sid)

    for r in survivors:
        if r.get("note"):  # curated -> preserve, scrub only
            r["note"] = scrub_note(r["note"])
            continue
        sid = r["serp_id"][:12]
        unique = [p for p in r["_sig"] if len(pair_carriers[p]) == 1]
        rare = [p for p in r["_sig"] if len(pair_carriers[p]) == 2]
        layout = r["_layout"]
        clauses = []
        if unique:
            clauses.append("sole carrier of " + ", ".join(unique))
        if layout and layout != "standard" and len(layout_carriers[str(layout)]) == 1:
            clauses.append(f"only {layout} layout in the corpus")
        if not unique and rare:
            clauses.append("one of two carriers of " + ", ".join(rare))
        if not clauses:
            notable = [p for p in r["_sig"] if not p.startswith(UBIQUITOUS)]
            if notable:
                clauses.append("coverage for " + ", ".join(notable[:4]))
            else:
                clauses.append("standard organic-results SERP")
        contribution = "; ".join(clauses)
        contribution = contribution[0].upper() + contribution[1:] + "."
        prov = f"Corpus capture, WebSearcher {r.get('version')}, {r.get('timestamp', '')[:10]}."
        r["note"] = f"{prov} {contribution}"


def emit(survivors: list[dict]) -> None:
    with bz2.open(OUT, "wt") as f:
        for r in survivors:
            rec = {k: v for k, v in r.items() if not k.startswith("_")}
            html = rec.pop("html")
            note = rec.pop("note")
            rec["note"] = note
            rec["html"] = html  # html last for readability
            f.write(orjson.dumps(rec).decode() + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only, do not write")
    args = ap.parse_args()

    survivors = load_sources()
    build_notes(survivors)

    print(f"survivors: {len(survivors)}  (dropped {len(DROPS)})")
    print(f"all have notes: {all(r.get('note') for r in survivors)}")
    print(f"versions: {dict(Counter(r.get('version') for r in survivors))}")
    print(f"layouts: {dict(Counter(str(r['_layout']) for r in survivors))}")
    tokens = [r["serp_id"][:12] for r in survivors if "google_abuse" in r.get("url", "")]
    print(f"urls with google_abuse token (kept as artifact): {tokens}")
    print("\nsample generated notes:")
    for r in survivors[:3] + survivors[-4:]:
        print(f"  [{r['serp_id'][:12]}] {r['note']}")

    if args.check:
        print("\n--check: not writing.")
        return
    emit(survivors)
    size = OUT.stat().st_size
    print(f"\nwrote {OUT} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
