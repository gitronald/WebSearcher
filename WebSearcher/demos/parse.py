"""Offline demo: parse a saved SERP ``.html`` file and print its components."""

import WebSearcher as ws

from ._common import _print_results_table


def parse(filepath: str) -> dict:
    """Offline demo: parse a saved SERP .html file and print its components."""
    soup = ws.load_soup(filepath)
    parsed = ws.parse_serp(soup)
    print(f"WebSearcher v{ws.__version__} | {filepath}\n")
    _print_results_table(parsed.get("results") or [], columns=("type", "title", "url"))
    return parsed
