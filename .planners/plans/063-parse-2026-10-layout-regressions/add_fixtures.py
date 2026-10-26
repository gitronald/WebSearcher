"""Append the plan 063 SERPs to the fixture corpus.

Copies the chosen records from a JSON-lines file of SERPs extracted from a
2026-10 crawl (by ``serp_id``) into ``tests/fixtures/serps.json.bz2``, giving
each a ``note`` and dropping its crawl batch id. Records already in the corpus
(by ``serp_id``) are skipped, so a re-run is a no-op.

    uv run python .planners/plans/063-parse-2026-10-layout-regressions/add_fixtures.py \\
        <samples.jsonl>
"""

import argparse
import bz2
from pathlib import Path

import orjson

CORPUS = Path("tests/fixtures/serps.json.bz2")
PROVENANCE = "Bulk corpus capture, WebSearcher 0.12.1 crawl 2026-10-26 (plan 063)"

# serp_id prefix -> what the record guards
NOTES = {
    "715c39159a62": (
        "2026-10 top stories, vertical list (g-section-with-header.yG4QQe, a.aJWbwf "
        "cards, one a video) with a trailing 'More news' link; guards the a.aJWbwf "
        "fallback in parse_top_stories and the div.MgUUmf cite / div.OSrXXb age."
    ),
    "67e221b91701": (
        "2026-10 top stories clustered into div.MmyPhf groups with an 'Also in the "
        "news' cluster (7 a.aJWbwf cards); guards the clustered layout."
    ),
    "0e2fb5edf0bb": (
        "2026-10 text ads: two div[data-text-ad] units in #tadsb with qmaLCb "
        "sitelinks and no div.uEierd wrapper; guards parse_ad_text. Also leads with "
        "the AI-overview banner wrapped in a qTdDb container, typed by "
        "ClassifyMain.ai_overview_wrapped_banner -> ai_overview/unavailable."
    ),
    "60bf643e2bf8": (
        "2026-10 text ad rendered mid-page (root div.yhQgZb, 'Sponsored result' "
        "heading, outside #tads/#tadsb); guards ClassifyMain.text_ad. Also carries "
        "the 'Find related products & services' module saved before its items "
        "loaded ('Thinking . . .' placeholder)."
    ),
    "2a3fd2155d93": (
        "Zero-result SERP whose only component is the AI-overview 'Thinking' / "
        "unavailable banner inside a qTdDb wrapper (with an empty #tads); guards "
        "ClassifyMain.ai_overview_wrapped_banner over knowledge_panel."
    ),
    "c3675409cbf7": (
        "Film 'Featured results' band rendered as div[role=group] (EGUFKc) with an "
        "inline-video trailer, images, and a VisualDigestDescription blurb; guards "
        "the role=group selector in knowledge_panel and the trailer row in "
        "_parse_visual_digest."
    ),
    "dc60ac7b1e9b": (
        "Sports tournament 'Bracket' module (span.mgAbYb level-2 heading); guards "
        "the 'Bracket' entry in ClassifyMain._KNOWLEDGE_SUBMODULE_HEADINGS."
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("serps", type=Path, help="extracted SERPs (JSON lines)")
    args = parser.parse_args()

    lines = bz2.open(CORPUS).read().splitlines()
    have = {orjson.loads(line)["serp_id"] for line in lines}

    added = []
    for line in args.serps.read_bytes().splitlines():
        record = orjson.loads(line)
        note = NOTES.get(record["serp_id"][:12])
        if note is None or record["serp_id"] in have:
            continue
        record["crawl_id"] = ""  # provenance lives in the note
        record["note"] = f"{PROVENANCE}. {note}"
        lines.append(orjson.dumps(record))
        have.add(record["serp_id"])
        added.append(f"{record['serp_id'][:12]} {record['qry']}")

    if added:
        CORPUS.write_bytes(bz2.compress(b"\n".join(lines) + b"\n"))
    print(f"added {len(added)}:", *added, sep="\n  ")


if __name__ == "__main__":
    main()
