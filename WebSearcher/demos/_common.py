"""Shared display and path helpers for the WebSearcher demos.

Stdlib only (no polars), so the demos run on a plain ``pip install WebSearcher``.
"""

from pathlib import Path

import WebSearcher as ws


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
