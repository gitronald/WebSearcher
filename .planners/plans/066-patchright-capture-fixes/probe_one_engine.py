"""Live probe for plan 066: run queries in sequence on one patchright engine.

For each query, records the request time, whether the capture holds ``#search``,
and whether the SERP's ``<title>`` names its own query (a mismatch means another
query's page was recorded). Runs against whatever WebSearcher the current
environment imports, so the same script times the base branch and this one.

With ``--ai-expand``, each row also records the logged ``ai_expand`` outcome and
compares the AI overview rows parsed from the page just before the show-more
click with those parsed after it, on the same page load. Both HTML captures are
saved next to the output, in ``<out stem>-html/``.

    uv run python .planners/plans/066-patchright-capture-fixes/probe_one_engine.py \
        --out data/plan-066/probe.jsonl --user-data-dir .ws_profile "query one" "query two"
"""

import argparse
import logging
import re
import statistics
import time
from pathlib import Path
from typing import Any, override

import orjson

import WebSearcher as ws
from WebSearcher import utils
from WebSearcher.searchers.patchright_searcher import PatchrightSearcher


class AiExpandOutcomes(logging.Handler):
    """Collect the messages of ``ai_expand`` log events."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.messages: list[str] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "event", None) == "ai_expand":
            self.messages.append(record.getMessage().removeprefix("SERP | ai_expand | "))


def ai_overview_summary(html: str) -> dict[str, Any]:
    """Counts over the AI overview rows parsed from ``html``."""
    rows = [r for r in ws.parse_serp(html)["results"] if r["type"] == "ai_overview"]
    details = [r.get("details") or {} for r in rows]
    return {
        "rows": len(rows),
        "sub_types": [r["sub_type"] for r in rows],
        "text_chars": sum(len(r.get("text") or "") for r in rows),
        "sections": sum(len(d.get("sections", [])) for d in details),
        "citations": sum(len(d.get("citations", [])) for d in details),
        "sources": sum(len(d.get("sources", [])) for d in details),
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("queries", nargs="+")
    parser.add_argument("--out", required=True, help="JSONL file to append results to")
    parser.add_argument("--ai-expand", action="store_true")
    parser.add_argument(
        "--user-data-dir",
        help="Persistent browser profile, e.g. one warmed with ws-demo; keeps its cookies",
    )
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    html_dir = out.parent / f"{out.stem}-html"
    times = []
    # As in ws-demo: a persistent profile keeps its cookies, so a challenge
    # solved while warming it is not cleared after the first query.
    patchright_config = (
        {"user_data_dir": args.user_data_dir, "clear_cookies": False} if args.user_data_dir else {}
    )
    log_config = {"console_level": "DEBUG"}
    with ws.SearchEngine(
        method="patchright", log_config=log_config, patchright_config=patchright_config
    ) as se:
        searcher = se.searcher
        assert isinstance(searcher, PatchrightSearcher)
        outcomes = AiExpandOutcomes()
        searcher.log.addHandler(outcomes)

        # Keep the page as it was just before the show-more click
        before: dict[str, str] = {}
        expand = searcher.expand_ai_overview

        def expand_keeping_before() -> str | None:
            before["html"] = searcher.page.content()
            return expand()

        searcher.expand_ai_overview = expand_keeping_before  # pyrefly: ignore[method-assign]

        for qry in args.queries:
            before.clear()
            outcomes.messages.clear()
            start = time.perf_counter()
            se.search(qry, ai_expand=args.ai_expand)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            html = se.serp["html"]
            title_node = utils.make_soup(html).css_first("title") if html else None
            title = title_node.text() if title_node is not None else ""
            row: dict[str, Any] = {
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
            if args.ai_expand:
                row["ai_expand"] = list(outcomes.messages)
            if "html" in before:
                slug = re.sub(r"[^a-z0-9]+", "-", qry.lower()).strip("-")
                html_dir.mkdir(parents=True, exist_ok=True)
                (html_dir / f"{slug}.before.html").write_text(before["html"])
                (html_dir / f"{slug}.after.html").write_text(html)
                ai_before = ai_overview_summary(before["html"])
                ai_after = ai_overview_summary(html)
                row["ai_rows_identical"] = ai_before.pop("results") == ai_after.pop("results")
                row["ai_before"] = ai_before
                row["ai_after"] = ai_after
            print(orjson.dumps(row).decode())
            with out.open("ab") as f:
                f.write(orjson.dumps(row) + b"\n")
            time.sleep(5)
    print(f"median seconds: {statistics.median(times):.2f} over {len(times)} queries")


if __name__ == "__main__":
    main()
