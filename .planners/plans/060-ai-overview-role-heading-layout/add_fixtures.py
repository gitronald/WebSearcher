"""Append the plan 060 AI-overview SERPs to the fixture corpus.

Copies the chosen records from a local run's ``serps.json`` into
``tests/fixtures/serps.json.bz2``, giving each a ``note``. Records already in
the corpus (by ``serp_id``) are skipped, so a re-run is a no-op.

    uv run python .planners/plans/060-ai-overview-role-heading-layout/add_fixtures.py \\
        data/demo-ws-v0.11.7a2-warm-profile/serps.json
"""

import argparse
import bz2
from pathlib import Path

import orjson

CORPUS = Path("tests/fixtures/serps.json.bz2")
PROVENANCE = "Corpus capture, WebSearcher 0.11.7a2, 2026-10-15 (plan 060)"

# serp_id prefix -> what the record guards
NOTES = {
    "ef30639b2b33": (
        "Role-heading AI overview (no Fzsovc/h2) with two sections, bullet lists, "
        "inline links, and a follow-up prompt; guards ai_overview typing over the "
        "embedded qTdDb knowledge controller."
    ),
    "adf0f7391ecc": (
        "Role-heading AI overview with three sections, a large source tray, and no "
        "follow-up prompt; no knowledge signal, so typed by the new-layout rule rather "
        "than the end-of-chain banner rule."
    ),
    "42bc62be2985": "Role-heading AI overview with no source tray (finance answer).",
    "3765fb676f3c": (
        "Role-heading AI overview that the banner rule typed as an empty ai_overview, "
        "and the flight-search widget headed 'Search flights' (es75Cc), which fell "
        "through to a hollow general row."
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("serps", type=Path, help="run serps.json (JSON lines)")
    args = parser.parse_args()

    lines = bz2.open(CORPUS).read().splitlines()
    have = {orjson.loads(line)["serp_id"] for line in lines}

    added = []
    for line in args.serps.read_bytes().splitlines():
        record = orjson.loads(line)
        note = NOTES.get(record["serp_id"][:12])
        if note is None or record["serp_id"] in have:
            continue
        record["note"] = f"{PROVENANCE}. {note}"
        lines.append(orjson.dumps(record))
        have.add(record["serp_id"])
        added.append(f"{record['serp_id'][:12]} {record['qry']}")

    if added:
        CORPUS.write_bytes(bz2.compress(b"\n".join(lines) + b"\n"))
    print(f"added {len(added)}:", *added, sep="\n  ")


if __name__ == "__main__":
    main()
