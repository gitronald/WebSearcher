"""Live probe for plan 066: run queries in sequence on one patchright engine.

For each query, records the request time, whether the capture holds ``#search``,
and whether the SERP's ``<title>`` names its own query (a mismatch means another
query's page was recorded). Runs against whatever WebSearcher the current
environment imports, so the same script times the base branch and this one.

    uv run python .planners/plans/066-patchright-capture-fixes/probe_one_engine.py \
        --out data/plan-066/probe.jsonl "query one" "query two"
"""

import argparse
import statistics
import time
from pathlib import Path

import orjson

import WebSearcher as ws
from WebSearcher import utils


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("queries", nargs="+")
    parser.add_argument("--out", required=True, help="JSONL file to append results to")
    parser.add_argument("--ai-expand", action="store_true")
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    times = []
    with ws.SearchEngine(method="patchright", log_config={"console_level": "DEBUG"}) as se:
        for qry in args.queries:
            start = time.perf_counter()
            se.search(qry, ai_expand=args.ai_expand)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            html = se.serp["html"]
            title_node = utils.make_soup(html).css_first("title") if html else None
            title = title_node.text() if title_node is not None else ""
            row = {
                "version": ws.__version__,
                "qry": qry,
                "seconds": round(elapsed, 2),
                "has_search": 'id="search"' in html,
                "title_matches": title.lower().startswith(qry.lower()),
                "title": title,
                "url": se.serp["url"],
                "response_code": se.serp["response_code"],
                "html_len": len(html),
            }
            print(orjson.dumps(row).decode())
            with out.open("ab") as f:
                f.write(orjson.dumps(row) + b"\n")
            time.sleep(5)
    print(f"median seconds: {statistics.median(times):.2f} over {len(times)} queries")


if __name__ == "__main__":
    main()
