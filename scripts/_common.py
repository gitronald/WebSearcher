"""Shared helpers for the dev/maintenance scripts in scripts/.

Salvaged and generalized from the retired scripts/ads-no-subtype/ probe before that
folder was removed. The probe's reusable kernel was: parse a stored SERP into its
component list, summarize (type, sub_type) coverage, flag components classified with
a type but no sub_type (a classifier-coverage gap), and cache/fetch raw SERP HTML in
parquet.

Adapted to the current parse_serp API, which returns
``{"results": [...], "features": {...}}`` -- the ads-no-subtype scripts predated that
change and treated parse_serp's return value as a bare list, so they no longer ran.

Heavy deps (WebSearcher, polars) are imported lazily inside the functions that need
them, so importing one helper does not drag in the others.
"""

from collections import Counter
from pathlib import Path

# -----------------------------------------------------------------------------
# Parsing
# -----------------------------------------------------------------------------


def parse_results(serp) -> list[dict]:
    """Parse a SERP (HTML string or selectolax Node) and return its component list.

    Wraps ``ws.parse_serp`` and unwraps the ``{"results": [...]}`` envelope, matching
    the ``parsed.get("results") or []`` idiom used across the dev scripts.
    """
    import WebSearcher as ws

    parsed = ws.parse_serp(serp)
    return parsed.get("results") or []


# -----------------------------------------------------------------------------
# Component checks  (pure functions over a parsed `results` list)
# -----------------------------------------------------------------------------


def type_subtype_counts(results: list[dict]) -> Counter:
    """Count parsed components by ``(type, sub_type)``; sub_type is None when absent."""
    return Counter((r.get("type"), r.get("sub_type")) for r in results)


def subtypes_for_type(results: list[dict], component_type: str) -> list[str]:
    """Sorted distinct non-null sub_types seen for one component type."""
    subtypes: set[str] = set()
    for r in results:
        if r.get("type") == component_type and (sub_type := r.get("sub_type")):
            subtypes.add(sub_type)
    return sorted(subtypes)


def components_missing_subtype(
    results: list[dict], component_type: str | None = None
) -> list[dict]:
    """Components classified with a type but a null/empty sub_type.

    The generalized check behind scripts/ads-no-subtype/: a typed component with no
    sub_type usually signals a classifier/parser coverage gap. Pass ``component_type``
    to scope to one type (e.g. ``"ad"``), or leave None to flag the gap across all
    types.
    """
    out = []
    for r in results:
        rtype = r.get("type")
        if rtype is None:
            continue
        if component_type is not None and rtype != component_type:
            continue
        if not r.get("sub_type"):
            out.append(r)
    return out


# -----------------------------------------------------------------------------
# Raw HTML cache / fetch  (parquet with columns: serp_id, html)
# -----------------------------------------------------------------------------


def load_html_cache(path) -> dict[str, str]:
    """Load a ``serp_id -> html`` mapping from a parquet cache (empty dict if absent)."""
    path = Path(path)
    if not path.exists():
        return {}
    import polars as pl

    df = pl.read_parquet(path, columns=["serp_id", "html"])
    return {row["serp_id"]: row["html"] for row in df.iter_rows(named=True)}


def save_html_cache(path, html_by_serp_id: dict[str, str]) -> int:
    """Write a ``serp_id -> html`` mapping to a parquet cache; returns rows written."""
    if not html_by_serp_id:
        return 0
    import polars as pl

    rows = [{"serp_id": sid, "html": html} for sid, html in html_by_serp_id.items()]
    pl.DataFrame(rows).write_parquet(Path(path))
    return len(rows)


def load_html_by_serp_ids(serps_parquet, serp_ids) -> dict[str, str]:
    """Batch-load ``serp_id -> html`` from a crawl's serps.parquet for the given ids.

    Scans rather than reads, so only matching rows are materialized -- the primitive
    for pulling HTML for a known set of SERPs out of a large parquet store. Loop over
    crawls/files at the call site to keep this free of any directory-layout assumption.
    """
    path = Path(serps_parquet)
    if not path.exists():
        return {}
    import polars as pl

    df = (
        pl.scan_parquet(path)
        .filter(pl.col("serp_id").is_in(list(serp_ids)))
        .select(["serp_id", "html"])
        .collect()
    )
    return {row["serp_id"]: row["html"] for row in df.iter_rows(named=True)}
