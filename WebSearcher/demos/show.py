"""Offline demo: show the parsed-results table for a saved SERP, selected by query.

Loads ``{data_dir}/serps.json`` (the output of ``ws-demo search``), finds the record
whose ``qry`` matches, parses its stored HTML fresh, and prints a ``type``/``title``/``url``
table. Runtime-deps-only (stdlib table helper, no polars), so it runs on a plain
``pip install WebSearcher``.
"""

import json
from pathlib import Path

import WebSearcher as ws

from ._common import _default_data_dir, _print_results_table


def _details_summary(d: dict | None) -> str:
    """One-line summary of a result's ``details`` payload (for the optional column)."""
    if not d:
        return "-"
    t = d.get("type", "?")
    if "items" in d:
        return f"{t} (n={len(d.get('items') or [])})"
    if t == "ratings":
        return f"ratings {d.get('rating')}/{d.get('scale')} ({d.get('n_reviews')})"
    if t == "place":
        parts = []
        if d.get("rating") is not None:
            parts.append(f"{d['rating']}({d.get('n_reviews')})")
        elif d.get("n_reviews") == 0:
            parts.append("no reviews")
        if d.get("price"):
            parts.append(d["price"])
        if d.get("category"):
            parts.append(d["category"])
        return "place " + " · ".join(parts) if parts else "place"
    if t == "video":
        bits = [v for v in (d.get("source"), d.get("channel"), d.get("publish_date")) if v]
        return "video" + (f" {' · '.join(bits)}" if bits else "")
    return t


def show(
    query: str | None = None,
    data_dir: str | None = None,
    list_queries: bool = False,
    details: bool = False,
    max_width: int = 60,
) -> dict | None:
    """Parse the saved SERP for ``query`` (from ``{data_dir}/serps.json``) and print it.

    Returns the parsed dict, or ``None`` when listing queries or no match is found.
    ``data_dir`` defaults to the current version's capture (``data/demo-ws-v{version}``).
    """
    ddir = Path(data_dir) if data_dir else _default_data_dir()
    fp = ddir / "serps.json"
    if not fp.exists():
        print(f'Not found: {fp}\nRun `ws-demo search "{query or "your query"}"` first.')
        return None

    queries: list[str] = []
    html: str | None = None
    with open(fp) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            qry = rec.get("qry")
            queries.append(qry)
            if query and qry == query:
                html = rec.get("html")

    if list_queries or not query:
        for q in queries:
            print(q)
        return None

    if html is None:
        print(f"No SERP found for query {query!r}. Use --list to see available queries.")
        return None

    parsed = ws.parse_serp(html)
    results = parsed.get("results") or []
    print(f"WebSearcher v{ws.__version__} | qry={query!r} | {len(results)} components\n")
    if details:
        rows = [{**r, "details": _details_summary(r.get("details"))} for r in results]
        columns: tuple[str, ...] = ("type", "title", "url", "details")
    else:
        rows = results
        columns = ("type", "title", "url")
    _print_results_table(rows, columns=columns, max_width=max_width)
    return parsed
