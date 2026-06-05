"""Survey AI Overview HTML structure across stored demo datasets.

Walks every `data/demo-ws-*/serps.json`, isolates each component that the current
classifier flags as an AI overview, and prints a structural summary so we can
design the new section-aware parser without re-parsing.
"""

import argparse
import json
import pathlib
from collections import Counter

from WebSearcher import make_soup
from WebSearcher._slx import Node, class_tokens, get_text, subtree_css, subtree_first
from WebSearcher.classifiers.main import ClassifyMain
from WebSearcher.extractors import Extractor


def iter_ai_overviews(serps_path: pathlib.Path):
    with open(serps_path) as f:
        for line in f:
            rec = json.loads(line)
            html = rec.get("html")
            if not html:
                continue
            soup = make_soup(html)
            extractor = Extractor(soup)
            extractor.extract_components()
            for cmpt in extractor.components:
                if cmpt.section != "main":
                    continue
                if ClassifyMain.ai_overview(cmpt.elem) == "ai_overview":
                    yield rec.get("qry", ""), rec.get("serp_id", ""), cmpt.elem


def summarize(cmpt: Node) -> dict:
    out: dict = {}

    h2 = subtree_first(cmpt, "h2")
    out["h2"] = get_text(h2, " ", strip=True) if h2 else None

    headings = []
    for h in subtree_css(cmpt, '[role="heading"]'):
        level = h.attributes.get("aria-level")
        text = get_text(h, " ", strip=True)
        if text:
            headings.append((level, text[:100]))
    out["headings"] = headings[:30]

    out["n_fzsovc_blocks"] = len(subtree_css(cmpt, "div.Fzsovc"))

    anchors = subtree_css(cmpt, "a[href]")
    hrefs = [(a, a.attributes.get("href") or "") for a in anchors]
    out["n_anchors"] = len(anchors)
    out["n_anchors_real"] = sum(1 for _, h in hrefs if h != "#")
    out["n_anchors_search"] = sum(1 for _, h in hrefs if h.startswith("/search?"))
    out["n_anchors_fragment"] = sum(1 for _, h in hrefs if "#:~:text=" in h)
    out["n_anchors_with_text"] = sum(1 for a, h in hrefs if h != "#" and get_text(a, strip=True))

    classes = Counter()
    for d in subtree_css(cmpt, "div[class]"):
        for c in class_tokens(d):
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
