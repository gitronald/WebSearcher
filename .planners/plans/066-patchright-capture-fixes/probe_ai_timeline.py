"""Live probe for plan 066: how long after ``#search`` does the AI overview keep loading?

For each query, navigates one patchright page and, from the moment ``#search``
appears, captures the HTML at fixed offsets (``OFFSETS``) without clicking
anything. Each capture is parsed after the schedule ends, so parsing never
delays it. A row per query records:

- ``search_at``: seconds from the start of ``goto`` to ``#search``
- ``dcl_at`` / ``load_at``: DOMContentLoaded and load, from the browser's
  navigation timing, on the same clock
- ``idle_at``: the first moment after load with no request in flight for
  500 ms, from a log of request events
- ``first_quiet_at``: the same, from the start of ``goto``. The driver's
  ``networkidle`` fires once, at the first such stretch, even before load, so
  an earlier value than ``idle_at`` means the settle step's network-idle wait
  would return before the AI overview finished
- ``snapshots``: per offset, the AI overview counts, the requests in flight,
  whether the parsed AI overview rows equal the last capture's, and two
  candidate signals for a targeted wait: ``body`` (``div.mZJni`` present) and
  ``generating`` (``role=progressbar`` elements labelled "Generating" that the
  browser renders visible, checked live: a stylesheet hides them, so saved HTML
  cannot show it)
- ``first_ai_at`` / ``stable_at``: the first offset with an AI overview row, and
  the offset from which every capture matches the last one
- ``inflight_at_end``: the requests still open when the last capture is taken
  (what keeps a page from going quiet), ``long_requests``: requests open for
  more than ``LONG_REQUEST_S`` (a streamed overview), and ``after_load``: the
  requests started after load, counted by URL. URLs are recorded as host and
  path, without the query string

The first and last captures are saved in ``<out stem>-html/``.

    uv run python .planners/plans/066-patchright-capture-fixes/probe_ai_timeline.py \
        --out data/plan-066/timeline.jsonl --user-data-dir .ws_profile "query one" "query two"
"""

import argparse
import collections
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import orjson

import WebSearcher as ws
from WebSearcher import utils
from WebSearcher.models.searches import SearchParams
from WebSearcher.searchers.patchright_searcher import PatchrightSearcher

# Seconds after #search appears at which the HTML is captured
OFFSETS = (0, 0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12)
IDLE_MS = 500
LONG_REQUEST_S = 1.0

# Live count of rendered "Generating" spinners
GENERATING_JS = (
    "() => [...document.querySelectorAll('[role=progressbar][aria-label=Generating]')]"
    ".filter((e) => e.checkVisibility()).length"
)


class NetworkLog:
    """Request start/end times on a page, in seconds from ``t0``.

    Sync-API events are delivered while patchright is waiting, so the probe
    waits with ``page.wait_for_timeout`` (never ``time.sleep``) between captures.
    """

    def __init__(self, page: Any, t0: float) -> None:
        self.page = page
        self.t0 = t0
        self.inflight: set[Any] = set()
        self.events: list[tuple[float, int]] = []  # (time, requests in flight after it)
        self.started: dict[Any, float] = {}
        self.finished: list[dict[str, Any]] = []
        self._handlers = {
            "request": self._start,
            "requestfinished": self._end,
            "requestfailed": self._end,
        }
        for name, handler in self._handlers.items():
            page.on(name, handler)

    def now(self) -> float:
        return time.perf_counter() - self.t0

    def _start(self, request: Any) -> None:
        self.inflight.add(request)
        self.started[request] = self.now()
        self.events.append((self.now(), len(self.inflight)))

    def _end(self, request: Any) -> None:
        self.inflight.discard(request)
        if request in self.started:
            self.finished.append(
                {**describe(request), "start": self.started.pop(request), "end": self.now()}
            )
        self.events.append((self.now(), len(self.inflight)))

    def requests_summary(self, load_at: float | None) -> dict[str, Any]:
        """Open, long-running, and after-load requests, times rounded to 0.01 s."""
        now = self.now()
        open_requests: list[dict[str, Any]] = [
            {**describe(r), "start": round(start, 2)} for r, start in self.started.items()
        ]
        long_requests = [
            {**r, "start": round(r["start"], 2), "end": round(r["end"], 2)}
            for r in self.finished
            if r["end"] - r["start"] > LONG_REQUEST_S
        ]
        long_requests += [
            {**r, "end": None} for r in open_requests if now - r["start"] > LONG_REQUEST_S
        ]
        after_load = collections.Counter(
            f"{r['type']} {r['url']}"
            for r in [*self.finished, *open_requests]
            if load_at is not None and r["start"] > load_at
        )
        return {
            "inflight_at_end": open_requests,
            "long_requests": sorted(long_requests, key=lambda r: r["start"]),
            "after_load": dict(after_load.most_common(15)),
        }

    def idle_at(self, after: float) -> float | None:
        """First time >= ``after`` with nothing in flight for ``IDLE_MS``."""
        prior = [n for t, n in self.events if t < after]
        later = [(t, n) for t, n in self.events if t >= after]
        quiet_starts = [after] if not prior or prior[-1] == 0 else []
        quiet_starts += [t for t, n in later if n == 0]
        for start in quiet_starts:
            # With nothing in flight, the next event is a request starting
            next_event = next((t for t, _ in later if t > start), self.now())
            if next_event - start >= IDLE_MS / 1000:
                return round(start, 2)
        return None

    def detach(self) -> None:
        for name, handler in self._handlers.items():
            self.page.remove_listener(name, handler)


def describe(request: Any) -> dict[str, Any]:
    """A request's resource type and URL, as host and path without the query string."""
    parts = urlsplit(request.url)
    url = f"{parts.netloc}{parts.path}" if parts.netloc else request.url[:60]
    return {"type": request.resource_type, "url": url}


def ai_overview(html: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Counts over the AI overview rows parsed from ``html``, and the rows."""
    rows = [r for r in ws.parse_serp(html)["results"] if r["type"] == "ai_overview"]
    details = [r.get("details") or {} for r in rows]
    soup = utils.make_soup(html)
    counts = {
        "rows": len(rows),
        "sub_types": [r["sub_type"] for r in rows],
        "text_chars": sum(len(r.get("text") or "") for r in rows),
        "sections": sum(len(d.get("sections", [])) for d in details),
        "sources": sum(len(d.get("sources", [])) for d in details),
        "complete_markers": html.count('data-complete="true"'),
        "body": soup.css_first("div.mZJni") is not None,
    }
    return counts, rows


def probe(searcher: PatchrightSearcher, qry: str, html_dir: Path) -> dict[str, Any]:
    url = SearchParams.create({"qry": qry}).url
    searcher.reset_page()
    page = searcher.page
    t0 = time.perf_counter()
    net = NetworkLog(page, t0)
    row: dict[str, Any] = {"qry": qry}
    try:
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("#search", timeout=15_000)
        except Exception as e:
            row["error"] = f"no #search: {e}"
            return row
        search_at = net.now()
        row["search_at"] = round(search_at, 2)

        captures: list[tuple[float, int, str, str, int]] = []
        for offset in OFFSETS:
            wait_ms = (search_at + offset - net.now()) * 1000
            if wait_ms > 0:
                page.wait_for_timeout(wait_ms)
            at = net.now() - search_at
            html = searcher.page_content(require_search=False)
            generating = page.evaluate(GENERATING_JS)
            captures.append((at, len(net.inflight), page.url, html, generating))

        timing = page.evaluate(
            "() => { const n = performance.getEntriesByType('navigation')[0];"
            " return n ? [n.domContentLoadedEventEnd, n.loadEventEnd] : [0, 0]; }"
        )
        # Navigation timing counts from navigationStart, a few ms after goto starts
        row["dcl_at"] = round(timing[0] / 1000, 2) if timing[0] else None
        row["load_at"] = round(timing[1] / 1000, 2) if timing[1] else None
        row["idle_at"] = net.idle_at(row["load_at"] or search_at)
        row["first_quiet_at"] = net.idle_at(0.0)
        row.update(net.requests_summary(row["load_at"]))
    finally:
        net.detach()

    parsed = [ai_overview(c[3]) for c in captures]
    final_rows = parsed[-1][1]
    snapshots = []
    for (at, inflight, page_url, html, generating), (counts, rows) in zip(
        captures, parsed, strict=True
    ):
        snapshots.append(
            {
                "at": round(at, 2),
                "inflight": inflight,
                "url_changed": page_url != captures[0][2],
                "has_search": 'id="search"' in html,
                "generating": generating,
                **counts,
                "same_as_final": rows == final_rows,
            }
        )
    row["snapshots"] = snapshots
    row["first_ai_at"] = next((s["at"] for s in snapshots if s["rows"]), None)
    stable = len(snapshots)
    while stable > 0 and snapshots[stable - 1]["same_as_final"]:
        stable -= 1
    row["stable_at"] = snapshots[stable]["at"] if stable < len(snapshots) else None

    slug = re.sub(r"[^a-z0-9]+", "-", qry.lower()).strip("-")
    html_dir.mkdir(parents=True, exist_ok=True)
    (html_dir / f"{slug}.first.html").write_text(captures[0][3])
    (html_dir / f"{slug}.last.html").write_text(captures[-1][3])
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("queries", nargs="+")
    parser.add_argument("--out", required=True, help="JSONL file to append results to")
    parser.add_argument(
        "--user-data-dir",
        help="Persistent browser profile, e.g. one warmed with ws-demo; keeps its cookies",
    )
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    html_dir = out.parent / f"{out.stem}-html"
    patchright_config = (
        {"user_data_dir": args.user_data_dir, "clear_cookies": False} if args.user_data_dir else {}
    )
    with ws.SearchEngine(method="patchright", patchright_config=patchright_config) as se:
        searcher = se.searcher
        assert isinstance(searcher, PatchrightSearcher)
        for qry in args.queries:
            row = probe(searcher, qry, html_dir)
            with out.open("ab") as f:
                f.write(orjson.dumps(row) + b"\n")
            print(
                f"{qry}: from goto: #search {row.get('search_at')} s, load {row.get('load_at')}, "
                f"first quiet {row.get('first_quiet_at')}, idle after load {row.get('idle_at')} | "
                f"from #search: AI first {row.get('first_ai_at')}, "
                f"stable {row.get('stable_at')} {row.get('error', '')}"
            )
            for r in row.get("long_requests", []):
                print(f"  long: {r['start']}-{r['end']} s {r['type']} {r['url']}")
            for r in row.get("inflight_at_end", []):
                print(f"  open at end: since {r['start']} s {r['type']} {r['url']}")
            for s in row.get("snapshots", []):
                print(
                    f"  +{s['at']:5.2f}s inflight={s['inflight']:3} rows={s['rows']} "
                    f"text={s['text_chars']:5} sections={s['sections']:2} "
                    f"sources={s['sources']:2} complete={s['complete_markers']:3} "
                    f"body={s['body']!s:5} generating={s['generating']} "
                    f"final={s['same_as_final']}"
                )
            time.sleep(5)


if __name__ == "__main__":
    main()
