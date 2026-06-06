"""Demo: search one query via the ``requests`` method with a custom header set."""

from pathlib import Path

import WebSearcher as ws

from ._common import _default_data_dir, _print_results_table

MODIFIED_HEADERS = {
    "Host": "www.google.com",
    "Referer": "https://www.google.com/",
    "Accept": "*/*",
    "Accept-Encoding": "gzip,deflate,br",
    "Accept-Language": "en-US,en;q=0.5",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0",
}


def headers(query: str, data_dir: str | None = None):
    """Search and parse one query via the requests method with a custom header set."""
    data_path = Path(data_dir) if data_dir else _default_data_dir()
    data_path.mkdir(parents=True, exist_ok=True)
    fps = {k: data_path / f"{k}.json" for k in ("serps", "parsed")}
    print(f"WebSearcher v{ws.__version__} | Search Query: {query} | Output: {data_path}")

    se = ws.SearchEngine(method="requests", requests_config={"headers": MODIFIED_HEADERS})
    se.search(query)
    se.parse_serp()
    se.save_serp(append_to=fps["serps"])
    se.save_parsed(append_to=fps["parsed"])

    _print_results_table(se.parsed.results)
    return se
