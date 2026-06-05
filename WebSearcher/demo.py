"""Runnable demos, shipped inside the package so they work after `pip install WebSearcher`.

Absorbed from the old `scripts/demo_*.py` (plan 033). Those imported `polars` and `typer`,
which are dev-only dependencies, and were wired as `scripts.*` console entry points that the
wheel never shipped -- so the documented `demo-search` command failed on a clean install. This
module depends only on WebSearcher's runtime deps: it prints results with a small stdlib table
helper instead of polars and uses `argparse` instead of typer.

Run a demo from the CLI::

    python -m WebSearcher.demo parse path/to/serp.html      # offline: parse a saved SERP
    python -m WebSearcher.demo search "why is the sky blue?"
    python -m WebSearcher.demo headers "pizza near me"      # requests method, custom headers
    python -m WebSearcher.demo locations pizza              # localized search (downloads geotargets)

`demo-search` is the same as the `search` subcommand. The runner functions (`parse`, `search`,
`headers`, `locations`) also return the parsed output / SearchEngine for interactive use.
"""

import argparse
import csv
from pathlib import Path

import WebSearcher as ws

MODIFIED_HEADERS = {
    "Host": "www.google.com",
    "Referer": "https://www.google.com/",
    "Accept": "*/*",
    "Accept-Encoding": "gzip,deflate,br",
    "Accept-Language": "en-US,en;q=0.5",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0",
}


# -----------------------------------------------------------------------------
# Display helpers (stdlib, no polars)
# -----------------------------------------------------------------------------


def _print_results_table(
    results: list[dict],
    columns: tuple[str, ...] = ("type", "sub_type", "title", "url"),
    max_width: int = 80,
) -> None:
    """Print selected columns of parsed results as a plain-text aligned table."""
    if not results:
        print("(no results)")
        return

    def cell(value) -> str:
        s = "" if value is None else str(value)
        return s if len(s) <= max_width else s[: max_width - 3] + "..."

    rows = [[cell(r.get(c)) for c in columns] for r in results]
    widths = [max(len(columns[i]), *(len(row[i]) for row in rows)) for i in range(len(columns))]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*columns))
    print(fmt.format(*("-" * w for w in widths)))
    for row in rows:
        print(fmt.format(*row))


def _default_data_dir() -> Path:
    return Path("data") / f"demo-ws-v{ws.__version__}"


def _chrome_version() -> str:
    """Best-effort installed-Chrome version for the search header (never raises)."""
    try:
        from .search_methods.selenium_searcher import detect_chrome_version

        return detect_chrome_version() or "unknown"
    except Exception:
        return "unknown"


def _find_location(csv_path: Path, canonical_name: str) -> dict | None:
    """Return the geotargets row whose 'Canonical Name' matches, or None (stdlib csv)."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("Canonical Name") == canonical_name:
                return row
    return None


# -----------------------------------------------------------------------------
# Demos
# -----------------------------------------------------------------------------


def parse(filepath: str) -> dict:
    """Offline demo: parse a saved SERP .html file and print its components."""
    soup = ws.load_soup(filepath)
    parsed = ws.parse_serp(soup)
    print(f"WebSearcher v{ws.__version__} | {filepath}\n")
    _print_results_table(parsed.get("results") or [], columns=("type", "title", "url"))
    return parsed


def search(
    query: str = "why is the sky blue?",
    method: str = "selenium",
    data_dir: str | None = None,
    headless: bool = False,
    use_subprocess: bool = False,
    version_main: int | None = None,
    ai_expand: bool = True,
    driver_executable_path: str = "",
):
    """Search and parse a single query (selenium or requests), saving serps/parsed/searches."""
    data_path = Path(data_dir) if data_dir else _default_data_dir()
    data_path.mkdir(parents=True, exist_ok=True)
    fps = {k: data_path / f"{k}.json" for k in ("serps", "parsed", "searches")}

    header = f"WebSearcher v{ws.__version__}\nSearch Query: {query}\n"
    if method == "selenium":
        header += f"Chrome Version: {_chrome_version()}\n"
    header += f"Output Dir: {data_path}\n"
    print(header)

    se = ws.SearchEngine(
        method=method,
        selenium_config={
            "headless": headless,
            "use_subprocess": use_subprocess,
            "driver_executable_path": driver_executable_path,
            "version_main": version_main,
        },
    )
    se.search(query, ai_expand=ai_expand)
    se.parse_serp()
    se.save_serp(append_to=fps["serps"])
    se.save_search(append_to=fps["searches"])
    se.save_parsed(append_to=fps["parsed"])

    _print_results_table(se.parsed.results)
    return se


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


def locations(
    query: str = "pizza",
    canonical_name: str = "Boston,Massachusetts,United States",
    locations_dir: str = "data/google_locations",
    data_dir: str = "data/html",
):
    """Localization demo: download geotargets, resolve a canonical name, run a localized search."""
    loc_dir = Path(locations_dir)
    loc_dir.mkdir(parents=True, exist_ok=True)
    ws.download_locations(loc_dir)
    csv_path = sorted(loc_dir.iterdir())[-1]  # latest download

    row = _find_location(csv_path, canonical_name)
    if row is None:
        print(f"Canonical name not found in {csv_path.name}: {canonical_name!r}")
        return None
    print(f"Location: {row['Canonical Name']} (Criteria ID {row['Criteria ID']})")

    se = ws.SearchEngine()
    se.search(query, location=canonical_name)
    se.parse_serp()

    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    se.save_search(append_to=data_path / "searches.json")
    se.save_serp(save_dir=data_path)

    _print_results_table(se.parsed.results, columns=("type", "title"))
    return se


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def _add_search_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("query", nargs="?", default="why is the sky blue?", help="Search query")
    p.add_argument(
        "method",
        nargs="?",
        default="selenium",
        choices=["selenium", "requests"],
        help="Search method",
    )
    p.add_argument("--data-dir", default=None, help="Directory to save outputs")
    p.add_argument("--headless", action="store_true", help="Run browser headless")
    p.add_argument("--use-subprocess", action="store_true", help="Run browser in a subprocess")
    p.add_argument(
        "--version-main", type=int, default=None, help="Chrome major version (auto if unset)"
    )
    p.add_argument(
        "--no-ai-expand", dest="ai_expand", action="store_false", help="Do not expand AI overviews"
    )
    p.add_argument("--driver-executable-path", default="", help="Path to ChromeDriver")


def _run_search(args: argparse.Namespace) -> None:
    search(
        args.query,
        args.method,
        data_dir=args.data_dir,
        headless=args.headless,
        use_subprocess=args.use_subprocess,
        version_main=args.version_main,
        ai_expand=args.ai_expand,
        driver_executable_path=args.driver_executable_path,
    )


def main(argv: list[str] | None = None) -> None:
    """CLI dispatcher for `python -m WebSearcher.demo <command>`."""
    parser = argparse.ArgumentParser(
        prog="python -m WebSearcher.demo", description="WebSearcher demos."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Parse a saved SERP .html file (offline)")
    p_parse.add_argument("filepath", help="Path to a saved SERP .html file")

    _add_search_args(sub.add_parser("search", help="Search and parse one query"))

    p_headers = sub.add_parser("headers", help="Search one query via requests with custom headers")
    p_headers.add_argument("query", help="Search query")
    p_headers.add_argument("--data-dir", default=None, help="Directory to save outputs")

    p_loc = sub.add_parser("locations", help="Localized search demo (downloads geotargets)")
    p_loc.add_argument("query", nargs="?", default="pizza", help="Search query")
    p_loc.add_argument(
        "--location",
        dest="canonical_name",
        default="Boston,Massachusetts,United States",
        help="Canonical geotarget name",
    )
    p_loc.add_argument(
        "--locations-dir", default="data/google_locations", help="Geotargets download dir"
    )
    p_loc.add_argument("--data-dir", default="data/html", help="Directory to save outputs")

    args = parser.parse_args(argv)
    if args.command == "parse":
        parse(args.filepath)
    elif args.command == "search":
        _run_search(args)
    elif args.command == "headers":
        headers(args.query, data_dir=args.data_dir)
    elif args.command == "locations":
        locations(
            args.query,
            canonical_name=args.canonical_name,
            locations_dir=args.locations_dir,
            data_dir=args.data_dir,
        )


def search_cli(argv: list[str] | None = None) -> None:
    """Console-script entry point for `demo-search`: search and parse one query."""
    parser = argparse.ArgumentParser(prog="demo-search", description="Search and parse one query.")
    _add_search_args(parser)
    _run_search(parser.parse_args(argv))


if __name__ == "__main__":
    main()
