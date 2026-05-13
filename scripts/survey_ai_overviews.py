"""Survey AI Overview HTML structure across stored demo datasets.

Walks every `data/demo-ws-*/serps.json`, isolates each component that the current
classifier flags as an AI overview, and prints a structural summary so we can
design the new section-aware parser without re-parsing.
"""

import argparse
import json
import pathlib
from collections import Counter

import bs4

from WebSearcher.classifiers.main import ClassifyMain
from WebSearcher.extractors import Extractor


def iter_ai_overviews(serps_path: pathlib.Path):
    with open(serps_path) as f:
        for line in f:
            rec = json.loads(line)
            html = rec.get("html")
            if not html:
                continue
            soup = bs4.BeautifulSoup(html, "lxml")
            extractor = Extractor(soup)
            extractor.extract_components()
            for cmpt in extractor.components:
                if cmpt.section != "main":
                    continue
                if ClassifyMain.ai_overview(cmpt.elem) == "knowledge":
                    yield rec.get("qry", ""), rec.get("serp_id", ""), cmpt.elem


def summarize(cmpt: bs4.element.Tag) -> dict:
    out: dict = {}

    h2 = cmpt.find("h2")
    out["h2"] = h2.get_text(" ", strip=True) if h2 else None

    headings = []
    for h in cmpt.find_all(attrs={"role": "heading"}):
        level = h.attrs.get("aria-level")
        text = h.get_text(" ", strip=True)
        if text:
            headings.append((level, text[:100]))
    out["headings"] = headings[:30]

    fzsovc = cmpt.find_all("div", {"class": "Fzsovc"})
    out["n_fzsovc_blocks"] = len(fzsovc)

    anchors = cmpt.find_all("a", href=True)
    out["n_anchors"] = len(anchors)
    out["n_anchors_real"] = sum(1 for a in anchors if a["href"] != "#")
    out["n_anchors_search"] = sum(1 for a in anchors if a["href"].startswith("/search?"))
    out["n_anchors_fragment"] = sum(1 for a in anchors if "#:~:text=" in a["href"])
    out["n_anchors_with_text"] = sum(
        1 for a in anchors if a["href"] != "#" and a.get_text(strip=True)
    )

    classes = Counter()
    for d in cmpt.find_all("div", class_=True):
        for c in d.attrs.get("class", []):
            classes[c] += 1
    out["top_classes"] = classes.most_common(15)

    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-glob",
        default="data/demo-ws-*/serps.json",
        help="Glob for serps.json files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Print full details for the first N overviews per dataset",
    )
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=None,
        help="Restrict to specific dataset basenames (e.g. demo-ws-v0.6.10a0)",
    )
    args = parser.parse_args()

    root = pathlib.Path.cwd()
    paths = sorted(root.glob(args.data_glob))
    if args.datasets:
        paths = [p for p in paths if p.parent.name in args.datasets]

    grand_total = 0
    for p in paths:
        print(f"\n========== {p.parent.name} ==========")
        n = 0
        heading_lvl_counter: Counter = Counter()
        for qry, serp_id, cmpt in iter_ai_overviews(p):
            n += 1
            summary = summarize(cmpt)
            for level, _ in summary["headings"]:
                heading_lvl_counter[level] += 1
            if n <= args.limit:
                print(f"\n--- qry: {qry!r}  serp: {serp_id[:12]} ---")
                print(f"  h2: {summary['h2']!r}")
                print(f"  fzsovc blocks: {summary['n_fzsovc_blocks']}")
                print(
                    f"  anchors: total={summary['n_anchors']} real={summary['n_anchors_real']}"
                    f" with_text={summary['n_anchors_with_text']}"
                    f" /search?={summary['n_anchors_search']} fragments={summary['n_anchors_fragment']}"
                )
                print("  headings:")
                for level, text in summary["headings"]:
                    print(f"    [lvl={level}] {text}")
                print(f"  top classes: {summary['top_classes']}")
        print(f"\nTotal AI overviews in {p.parent.name}: {n}")
        if heading_lvl_counter:
            print(f"Heading aria-level distribution: {dict(heading_lvl_counter)}")
        grand_total += n
    print(f"\n=== Grand total AI overviews across {len(paths)} datasets: {grand_total} ===")


if __name__ == "__main__":
    main()
