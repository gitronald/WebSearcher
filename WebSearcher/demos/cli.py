"""argparse CLI for the ``ws-demo`` command (and ``python -m WebSearcher.demos``)."""

import argparse

from .headers import headers
from .locations import locations
from .parse import parse
from .search import search, searches
from .show import show


def _add_engine_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "method",
        nargs="?",
        default="selenium",
        choices=["selenium", "requests", "zendriver", "patchright", "playwright"],
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


def _add_search_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("query", nargs="?", default="why is the sky blue?", help="Search query")
    _add_engine_args(p)


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
    """CLI dispatcher for the `ws-demo` command (and `python -m WebSearcher.demos`)."""
    parser = argparse.ArgumentParser(prog="ws-demo", description="WebSearcher demos.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Parse a saved SERP .html file (offline)")
    p_parse.add_argument("filepath", help="Path to a saved SERP .html file")

    p_show = sub.add_parser(
        "show", help="Show the parsed-results table for a saved query (offline)"
    )
    p_show.add_argument("query", nargs="?", default=None, help="Query whose saved SERP to show")
    p_show.add_argument(
        "--data-dir",
        default=None,
        help="Directory containing serps.json (default: current version)",
    )
    p_show.add_argument(
        "--list", dest="list_queries", action="store_true", help="List saved queries"
    )
    p_show.add_argument("--details", action="store_true", help="Include the details summary column")
    p_show.add_argument("--max-width", type=int, default=60, help="Max cell width (chars)")

    _add_search_args(sub.add_parser("search", help="Search and parse one query"))

    p_searches = sub.add_parser(
        "searches", help="Search a battery of queries spanning SERP component types"
    )
    _add_engine_args(p_searches)
    p_searches.add_argument(
        "--types", nargs="*", default=None, help="Only run queries for these target types"
    )
    p_searches.add_argument(
        "--delay", type=float, default=30.0, help="Seconds between queries (plus jitter)"
    )

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
        "--locations-dir",
        default=None,
        help="Geotargets download dir (default: data/demo-ws-v{version}/)",
    )
    p_loc.add_argument("--data-dir", default="data/html", help="Directory to save outputs")

    args = parser.parse_args(argv)
    if args.command == "parse":
        parse(args.filepath)
    elif args.command == "show":
        show(
            args.query,
            data_dir=args.data_dir,
            list_queries=args.list_queries,
            details=args.details,
            max_width=args.max_width,
        )
    elif args.command == "search":
        _run_search(args)
    elif args.command == "searches":
        searches(
            types=args.types,
            method=args.method,
            data_dir=args.data_dir,
            headless=args.headless,
            use_subprocess=args.use_subprocess,
            version_main=args.version_main,
            ai_expand=args.ai_expand,
            driver_executable_path=args.driver_executable_path,
            delay=args.delay,
        )
    elif args.command == "headers":
        headers(args.query, data_dir=args.data_dir)
    elif args.command == "locations":
        locations(
            args.query,
            canonical_name=args.canonical_name,
            locations_dir=args.locations_dir,
            data_dir=args.data_dir,
        )
