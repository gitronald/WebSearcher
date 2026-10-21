"""Count AI-overview answers embedded in people-also-ask components.

For each ``people_also_ask`` component, finds the ``div.mZJni`` overview bodies
inside it, the question (``data-q``) each sits under, and whether that is the
component's first question. Reads JSON lines, plain or bz2.

    uv run python .planners/plans/061-paa-embedded-ai-overview/probe_paa_aio.py \\
        tests/fixtures/serps.json.bz2 [--show N]
"""

import argparse
import bz2
from collections import Counter
from pathlib import Path

import orjson

from WebSearcher import utils
from WebSearcher._slx import get_text
from WebSearcher.extractors import Extractor


def _lines(path: Path) -> list[bytes]:
    raw = bz2.open(path).read() if path.suffix == ".bz2" else path.read_bytes()
    return raw.splitlines()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("serps", type=Path, help="serps JSON lines (.json or .json.bz2)")
    parser.add_argument("--show", type=int, default=2, help="examples to print")
    args = parser.parse_args()

    stats: Counter[str] = Counter()
    shown = 0
    for line in _lines(args.serps):
        record = orjson.loads(line)
        extractor = Extractor(utils.make_soup(record["html"]))
        extractor.extract_components()
        for cmpt in extractor.components:
            cmpt.classify_component()
            if cmpt.type != "people_also_ask":
                continue
            stats["paa"] += 1
            questions = [q.attributes.get("data-q") for q in cmpt.elem.css("[data-q]")]
            blocks = cmpt.elem.css("div.mZJni")
            stats["paa_with_overview"] += bool(blocks)
            for block in blocks:
                owner = block
                while owner is not None and "data-q" not in owner.attributes:
                    owner = owner.parent
                question = owner.attributes.get("data-q") if owner is not None else None
                stats["overviews"] += 1
                stats["under_first_question"] += bool(questions) and question == questions[0]
                stats["citation_buttons"] += len(block.css("button.vDOt8c, button.rBl3me"))
                stats["source_cards"] += len(block.css("div[data-src-id]"))
                if shown < args.show:
                    shown += 1
                    text = get_text(block, " ", strip=True) or ""
                    print(f"{record['serp_id'][:12]} {record['qry']!r} | question: {question!r}")
                    print(f"    {text[:240]}")
    print(dict(stats))


if __name__ == "__main__":
    main()
