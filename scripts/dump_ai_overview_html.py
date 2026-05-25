"""Dump the raw HTML of selected AI overview components for parser design.

Filters to the "real" AI overview (skips the 'Related Links' expansion that also
contains Fzsovc) and writes one HTML file per overview under
`/tmp/ai_overviews/{dataset}/{serp_id}_{rank}.html` for offline inspection.
"""

import argparse
import json
import pathlib

import bs4

from WebSearcher.classifiers.main import ClassifyMain
from WebSearcher.extractors import Extractor


def is_real_ai_overview(cmpt_elem: bs4.element.Tag) -> bool:
    if ClassifyMain.ai_overview(cmpt_elem) != "ai_overview":
        return False
    h2 = cmpt_elem.find("h2")
    if h2 and h2.get_text(strip=True) == "Related Links":
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-glob", default="data/demo-ws-*/serps.json")
    parser.add_argument("--out-dir", default="/tmp/ai_overviews")
    parser.add_argument("--max-per-dataset", type=int, default=3)
    args = parser.parse_args()

    out_root = pathlib.Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    for serps_path in sorted(pathlib.Path.cwd().glob(args.data_glob)):
        ds = serps_path.parent.name
        out_ds = out_root / ds
        out_ds.mkdir(parents=True, exist_ok=True)
        written = 0
        with open(serps_path) as f:
            for line in f:
                if written >= args.max_per_dataset:
                    break
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
                    if not is_real_ai_overview(cmpt.elem):
                        continue
                    qry = (rec.get("qry") or "")[:40].replace("/", "_")
                    serp_id = (rec.get("serp_id") or "")[:12]
                    fname = f"{serp_id}__{qry}__r{cmpt.cmpt_rank}.html"
                    (out_ds / fname).write_text(cmpt.elem.prettify())
                    print(f"wrote {out_ds / fname}")
                    written += 1
                    break


if __name__ == "__main__":
    main()
