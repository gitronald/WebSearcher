"""Probe AI-overview layouts in a SERP file (plan 060).

Reads a JSON-lines SERP file (``serps.json`` or ``serps.json.bz2``). For each
SERP that carries the AI overview controller (``jscontroller="EYwa3d"``), print
its layout (old: ``div.Fzsovc`` or an ``h2`` "AI Overview"; new: only a
``[role="heading"]`` "AI Overview"), the type the component holding the
controller is classified as, which classifiers would claim it, and counts of
the CSS markers ``parse_ai_overview`` reads. ``--summary`` prints only the
layout counts.

    uv run python .planners/plans/060-ai-overview-role-heading-layout/probe_aio_layout.py \\
        data/demo-ws-v0.11.7a2-warm-profile/serps.json
    uv run python .planners/plans/060-ai-overview-role-heading-layout/probe_aio_layout.py \\
        tests/fixtures/serps.json.bz2 --summary
"""

import argparse
import bz2
from collections import Counter
from pathlib import Path
from typing import Any

import orjson
from selectolax.lexbor import LexborNode as Node

import WebSearcher as ws
from WebSearcher._slx import get_text
from WebSearcher.classifiers.main import ClassifyMain

PARSER_MARKERS = [
    "div.mZJni",
    "div.rPeykc",
    "button.rBl3me",
    "ul.bTFeG",
    "li.CyMdWb",
    "div.Fzsovc",
    "div.hdzaWe",
    '[role="heading"]',
    "[data-src-id]",
]


def read_serps(path: Path) -> list[dict[str, Any]]:
    raw = bz2.open(path).read() if path.suffix == ".bz2" else path.read_bytes()
    return [orjson.loads(line) for line in raw.splitlines()]


def has_heading_text(node: Node, css: str, text: str = "AI Overview") -> bool:
    return any((get_text(h, strip=True) or "") == text for h in node.css(css))


def layout(soup: Node) -> str:
    old = soup.css_first("div.Fzsovc") is not None or has_heading_text(soup, "h2")
    new = has_heading_text(soup, '[role="heading"]')
    if old:
        return "old+new" if new else "old"
    return "new" if new else "none"


def probe(serp: dict[str, Any]) -> dict[str, Any] | None:
    soup = ws.make_soup(serp["html"])
    if soup.css_first('div[jscontroller="EYwa3d"]') is None:
        return None
    row: dict[str, Any] = {"qry": serp.get("qry"), "layout": layout(soup)}
    extractor = ws.Extractor(soup)
    extractor.extract_components()
    for cmpt in extractor.components:
        if cmpt.elem.css_first('div[jscontroller="EYwa3d"]') is None:
            continue
        cmpt.classify_component()
        elem: Node = cmpt.elem
        row["type"] = cmpt.type
        row["claims"] = {
            "ai_overview": ClassifyMain.ai_overview(elem),
            "knowledge_panel": ClassifyMain.knowledge_panel(elem),
            "ai_overview_banner": ClassifyMain.ai_overview_banner(elem),
        }
        row["markers"] = {css: len(elem.css(css)) for css in PARSER_MARKERS}
        break
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("serps", type=Path, help="serps.json or serps.json.bz2")
    parser.add_argument("--summary", action="store_true", help="Print layout counts only")
    args = parser.parse_args()

    counts: Counter[tuple[str, str]] = Counter()
    for i, serp in enumerate(read_serps(args.serps)):
        row = probe(serp)
        if row is None:
            continue
        counts[(row["layout"], row.get("type", "not extracted"))] += 1
        if not args.summary:
            print(f"{i:>3} {row['qry']!r}: layout={row['layout']} type={row.get('type')}")
            print(f"    claims={row.get('claims')}")
            print(f"    markers={row.get('markers')}")
    print("\n(layout, type of the component holding the controller): count")
    for key, n in sorted(counts.items()):
        print(f"  {key}: {n}")


if __name__ == "__main__":
    main()
