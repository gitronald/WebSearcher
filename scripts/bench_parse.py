"""Benchmark and profile parse_serp over the stored fixture corpus.

The profiling baseline that gates plan 023 (parse pipeline optimization). Reports
per-SERP median + median absolute deviation (parse times are right-skewed, so the
mean misleads) and inter-run spread to separate real deltas from noise. Run with
logging at WARNING so debug f-string formatting does not contaminate timings.

    uv run python scripts/bench_parse.py --iterations 50 --runs 5
    uv run python scripts/bench_parse.py --profile --profile-out parse.prof
"""

import bz2
import cProfile
import gc
import logging
import pstats
import statistics
import time
from pathlib import Path

import orjson
import typer

import WebSearcher as ws

app = typer.Typer(add_completion=False)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def load_records(fixtures: list[Path], limit: int | None) -> list[dict]:
    """Load SERP records from one or more bz2-compressed JSON-lines fixtures."""
    records: list[dict] = []
    for path in fixtures:
        with bz2.open(path, "rt") as f:
            records.extend(orjson.loads(line) for line in f)
    return records[:limit] if limit else records


def mad(values: list[float], center: float) -> float:
    """Median absolute deviation from a given center."""
    return statistics.median(abs(v - center) for v in values)


def time_parse(html: str, iterations: int) -> list[float]:
    """Time `iterations` parses of one SERP; gc paused to reduce jitter."""
    times = []
    gc.disable()
    try:
        for _ in range(iterations):
            t0 = time.perf_counter()
            ws.parse_serp(html)
            times.append((time.perf_counter() - t0) * 1000.0)  # ms
    finally:
        gc.enable()
    return times


@app.command()
def main(
    fixtures: list[Path] = typer.Option(
        None, "--fixtures", help="bz2 fixture paths (default: all tests/fixtures/serps-v*.json.bz2)"
    ),
    iterations: int = typer.Option(50, help="Parses per SERP per run"),
    runs: int = typer.Option(5, help="Full passes over the corpus (inter-run spread)"),
    limit: int = typer.Option(0, help="Cap number of SERPs (0 = all)"),
    profile: bool = typer.Option(False, "--profile", help="Run cProfile instead of timing"),
    profile_sort: str = typer.Option("tottime", help="cProfile sort key (tottime|cumulative)"),
    profile_out: Path = typer.Option(None, "--profile-out", help="Write .prof stats for snakeviz"),
    top: int = typer.Option(30, help="Rows of profile output to print"),
):
    """Benchmark or profile parse_serp over the fixture corpus."""
    logging.getLogger("WebSearcher").setLevel(logging.WARNING)

    paths = fixtures or sorted(FIXTURES_DIR.glob("serps-v*.json.bz2"))
    if not paths:
        typer.echo(f"No fixtures found in {FIXTURES_DIR}")
        raise typer.Exit(1)

    records = load_records(paths, limit or None)
    htmls = [r["html"] for r in records]
    typer.echo(f"Loaded {len(htmls)} SERPs from {len(paths)} fixture(s):")
    for p in paths:
        typer.echo(f"  {p.name}")

    # Warm up imports, caches, and the parser code paths (untimed).
    for html in htmls:
        ws.parse_serp(html)

    if profile:
        run_profile(htmls, iterations, profile_sort, profile_out, top)
    else:
        run_benchmark(htmls, iterations, runs)


def run_benchmark(htmls: list[str], iterations: int, runs: int) -> None:
    """Time the corpus over `runs` passes and report per-SERP and per-run stats."""
    typer.echo(f"\nBenchmark: {iterations} iterations x {runs} runs\n")

    run_totals = []  # total corpus ms per run (sum of per-SERP medians)
    last_per_serp: list[float] = []
    for run in range(runs):
        per_serp = [statistics.median(time_parse(html, iterations)) for html in htmls]
        total = sum(per_serp)
        run_totals.append(total)
        last_per_serp = per_serp
        typer.echo(
            f"  run {run + 1}/{runs}: corpus {total:8.1f} ms  median/SERP {statistics.median(per_serp):6.3f} ms"
        )

    # Per-SERP distribution from the final run.
    med = statistics.median(last_per_serp)
    typer.echo("\nPer-SERP parse time (final run):")
    typer.echo(f"  median {med:.3f} ms   MAD {mad(last_per_serp, med):.3f} ms")
    typer.echo(
        f"  min {min(last_per_serp):.3f}   p90 {percentile(last_per_serp, 90):.3f}   max {max(last_per_serp):.3f} ms"
    )

    # Inter-run spread tells us the noise floor for gating future changes.
    rt_med = statistics.median(run_totals)
    typer.echo("\nInter-run corpus total:")
    typer.echo(
        f"  median {rt_med:.1f} ms   MAD {mad(run_totals, rt_med):.1f} ms   spread {max(run_totals) - min(run_totals):.1f} ms"
    )
    typer.echo(
        f"  noise floor ~{2 * mad(run_totals, rt_med) / rt_med * 100:.1f}% (2x MAD); gate changes above this"
    )


def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolated percentile."""
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * pct / 100.0
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def run_profile(htmls: list[str], iterations: int, sort: str, out: Path | None, top: int) -> None:
    """cProfile the corpus and print top functions; optionally dump .prof."""
    typer.echo(f"\nProfiling {len(htmls)} SERPs x {iterations} iterations (sort={sort})\n")
    prof = cProfile.Profile()
    prof.enable()
    for _ in range(iterations):
        for html in htmls:
            ws.parse_serp(html)
    prof.disable()

    stats = pstats.Stats(prof).strip_dirs().sort_stats(sort)
    stats.print_stats(top)
    if out:
        pstats.Stats(prof).dump_stats(str(out))
        typer.echo(f"\nWrote {out} (open with: uv run snakeviz {out})")


if __name__ == "__main__":
    app()
