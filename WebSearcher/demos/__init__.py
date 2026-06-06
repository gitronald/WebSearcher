"""Runnable demos, shipped inside the package so they work after `pip install WebSearcher`.

Absorbed from the old `scripts/demo_*.py` (plan 033). Those imported `polars` and `typer`,
which are dev-only dependencies, and were wired as `scripts.*` console entry points that the
wheel never shipped -- so the documented demo command failed on a clean install. This package
depends only on WebSearcher's runtime deps: it prints results with a small stdlib table helper
instead of polars and uses `argparse` instead of typer.

Run a demo with the `ws-demo` console command (or `python -m WebSearcher.demos`)::

    ws-demo parse path/to/serp.html      # offline: parse a saved SERP file
    ws-demo show "election news"         # offline: parsed table for a saved query
    ws-demo search "why is the sky blue?"
    ws-demo searches                     # battery of queries spanning component types
    ws-demo headers "pizza near me"      # requests method, custom headers
    ws-demo locations pizza              # localized search (downloads geotargets)

The runner functions (`parse`, `show`, `search`, `searches`, `headers`, `locations`) also return the
parsed output / SearchEngine for interactive use; each lives in the like-named submodule.
"""

from .cli import main
from .headers import headers
from .locations import locations
from .parse import parse
from .search import QUERIES, search, searches
from .show import show

__all__ = ["main", "parse", "show", "search", "searches", "headers", "locations", "QUERIES"]
