"""Localization demo: download geotargets, resolve a canonical name, run a localized search."""

import csv
from pathlib import Path

import WebSearcher as ws

from ._common import _default_data_dir, _print_results_table


def _find_location(csv_path: Path, canonical_name: str) -> dict | None:
    """Return the geotargets row whose 'Canonical Name' matches, or None (stdlib csv)."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("Canonical Name") == canonical_name:
                return row
    return None


def locations(
    query: str = "pizza",
    canonical_name: str = "Boston,Massachusetts,United States",
    locations_dir: str | None = None,
    data_dir: str = "data/html",
):
    """Localization demo: download geotargets, resolve a canonical name, run a localized search."""
    loc_dir = Path(locations_dir) if locations_dir else _default_data_dir()
    loc_dir.mkdir(parents=True, exist_ok=True)
    ws.download_locations(loc_dir)
    csv_path = sorted(loc_dir.glob("geotargets-*.csv"))[-1]  # latest downloaded geotargets

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
