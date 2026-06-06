"""Benchmark and profile parse_serp over the stored fixture corpus.

The profiling baseline that gates parse-pipeline optimization. Reports per-SERP
median + median absolute deviation (parse times are right-skewed, so the mean
misleads) and inter-run spread to separate real deltas from noise. Run with logging
at WARNING so debug f-string formatting does not contaminate timings.

Every run appends a version/corpus/timing row to tests/benchmarks/results.jsonl so
cross-version comparisons come from data, not plan archaeology. Profile runs also
dump raw cProfile stats to tests/benchmarks/profiles/{id}.prof (gitignored) for
snakeviz. Pass --no-save for throwaway runs (e.g. quick smoke checks).

A dev tool: it reads tests/fixtures/ and writes tests/benchmarks/, so it only runs
from a repo checkout, not a bare wheel install. argparse / stdlib only (no typer),
so importing it never pulls a dev dependency into the package. Invoke from the repo
root:

    uv run python -m WebSearcher.bench --iterations 50 --runs 5
    uv run python -m WebSearcher.bench --profile
"""

import argparse
import bz2
import cProfile
import gc
import logging
import platform
import pstats
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

import WebSearcher as ws

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
BENCH_DIR = REPO_ROOT / "tests" / "benchmarks"
RESULTS_PATH = BENCH_DIR / "results.jsonl"
PROFILES_DIR = BENCH_DIR / "profiles"
SCHEMA_VERSION = 1


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


def git_info() -> dict:
    """Best-effort git sha/branch/dirty for stamping benchmark records."""

    def _git(*args: str) -> str:
        try:
            out = subprocess.run(
                ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5
            )
            return out.stdout.strip()
        except Exception:
            return ""

    return {
        "git_sha": _git("rev-parse", "--short", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
    }


def run_metadata(paths: list[Path], n_serps: int, iterations: int) -> dict:
    """Common version/corpus metadata stamped on every results.jsonl row.

    The `id` (UTC timestamp + short sha) doubles as the profile filename, so a
    results row and its .prof are always traceable to each other.
    """
    gi = git_info()
    now = datetime.now(UTC)
    return {
        "schema": SCHEMA_VERSION,
        "id": now.strftime("%Y%m%dT%H%M%SZ") + "_" + (gi["git_sha"] or "nogit"),
        "timestamp": now.isoformat(),
        "ws_version": getattr(ws, "__version__", None),
        "python": platform.python_version(),
        "fixtures": [p.name for p in paths],
        "n_serps": n_serps,
        "iterations": iterations,
        **gi,
    }


def append_result(record: dict) -> None:
    """Append one JSON record (newline-delimited) to the cumulative results log."""
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "ab") as f:
        f.write(orjson.dumps(record))
        f.write(b"\n")


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


def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolated percentile."""
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * pct / 100.0
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def run_benchmark(htmls: list[str], iterations: int, runs: int, meta: dict, save: bool) -> None:
    """Time the corpus over `runs` passes and report per-SERP and per-run stats."""
    print(f"\nBenchmark: {iterations} iterations x {runs} runs\n")

    run_totals = []  # total corpus ms per run (sum of per-SERP medians)
    last_per_serp: list[float] = []
    for run in range(runs):
        per_serp = [statistics.median(time_parse(html, iterations)) for html in htmls]
        total = sum(per_serp)
        run_totals.append(total)
        last_per_serp = per_serp
        print(
            f"  run {run + 1}/{runs}: corpus {total:8.1f} ms  median/SERP {statistics.median(per_serp):6.3f} ms"
        )

    # Per-SERP distribution from the final run.
    med = statistics.median(last_per_serp)
    print("\nPer-SERP parse time (final run):")
    print(f"  median {med:.3f} ms   MAD {mad(last_per_serp, med):.3f} ms")
    print(
        f"  min {min(last_per_serp):.3f}   p90 {percentile(last_per_serp, 90):.3f}   max {max(last_per_serp):.3f} ms"
    )

    # Inter-run spread tells us the noise floor for gating future changes.
    rt_med = statistics.median(run_totals)
    print("\nInter-run corpus total:")
    print(
        f"  median {rt_med:.1f} ms   MAD {mad(run_totals, rt_med):.1f} ms   spread {max(run_totals) - min(run_totals):.1f} ms"
    )
    print(
        f"  noise floor ~{2 * mad(run_totals, rt_med) / rt_med * 100:.1f}% (2x MAD); gate changes above this"
    )

    if save:
        record = {
            **meta,
            "kind": "benchmark",
            "runs": runs,
            "per_serp_median_ms": round(med, 4),
            "per_serp_mad_ms": round(mad(last_per_serp, med), 4),
            "per_serp_min_ms": round(min(last_per_serp), 4),
            "per_serp_p90_ms": round(percentile(last_per_serp, 90), 4),
            "per_serp_max_ms": round(max(last_per_serp), 4),
            "corpus_total_median_ms": round(rt_med, 4),
            "corpus_total_mad_ms": round(mad(run_totals, rt_med), 4),
            "corpus_total_spread_ms": round(max(run_totals) - min(run_totals), 4),
            "noise_floor_pct": round(2 * mad(run_totals, rt_med) / rt_med * 100, 4),
        }
        append_result(record)
        print(f"\nSaved benchmark row to {RESULTS_PATH.relative_to(REPO_ROOT)} (id={meta['id']})")


def profile_top(stats: Any, sort: str, top: int) -> list[dict]:
    """Top functions by the chosen sort key, as structured rows for the log.

    `stats` is typed Any because the runtime `.stats` dict (key -> (cc, nc, tt,
    ct, callers)) is not in pstats' typeshed stubs.
    """
    rows = [
        {
            "func": f"{fn}:{lineno}({func})",
            "ncalls": nc,
            "tottime": round(tt, 4),
            "cumtime": round(ct, 4),
        }
        for (fn, lineno, func), (_, nc, tt, ct, _) in stats.stats.items()
    ]
    rows.sort(key=lambda r: r["cumtime" if sort == "cumulative" else "tottime"], reverse=True)
    return rows[:top]


def run_profile(
    htmls: list[str], iterations: int, sort: str, out: Path | None, top: int, meta: dict, save: bool
) -> None:
    """cProfile the corpus, print top functions, and save the .prof + a results row."""
    print(f"\nProfiling {len(htmls)} SERPs x {iterations} iterations (sort={sort})\n")
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
        print(f"\nWrote {out} (open with: uv run snakeviz {out})")

    if save:
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        prof_path = PROFILES_DIR / f"{meta['id']}.prof"
        pstats.Stats(prof).dump_stats(str(prof_path))
        st: Any = stats  # totals live on the runtime object, not pstats' stubs
        record = {
            **meta,
            "kind": "profile",
            "sort": sort,
            "total_calls": st.total_calls,
            "primitive_calls": st.prim_calls,
            "total_seconds": round(st.total_tt, 4),
            "prof_path": str(prof_path.relative_to(REPO_ROOT)),
            "top": profile_top(st, sort, top),
        }
        append_result(record)
        print(
            f"\nSaved profile to {prof_path.relative_to(REPO_ROOT)} "
            f"and row to {RESULTS_PATH.relative_to(REPO_ROOT)} (id={meta['id']}); "
            f"open with: uv run snakeviz {prof_path.relative_to(REPO_ROOT)}"
        )


def main(argv: list[str] | None = None) -> None:
    """Benchmark or profile parse_serp over the fixture corpus."""
    p = argparse.ArgumentParser(
        prog="WebSearcher.bench",
        description="Benchmark or profile parse_serp over the fixture corpus.",
    )
    p.add_argument(
        "--fixtures",
        nargs="*",
        type=Path,
        default=None,
        help="bz2 fixture paths (default: all tests/fixtures/serps*.json.bz2)",
    )
    p.add_argument("--iterations", type=int, default=50, help="Parses per SERP per run")
    p.add_argument(
        "--runs", type=int, default=5, help="Full passes over the corpus (inter-run spread)"
    )
    p.add_argument("--limit", type=int, default=0, help="Cap number of SERPs (0 = all)")
    p.add_argument("--profile", action="store_true", help="Run cProfile instead of timing")
    p.add_argument(
        "--profile-sort", default="tottime", help="cProfile sort key (tottime|cumulative)"
    )
    p.add_argument(
        "--profile-out",
        type=Path,
        default=None,
        help="Also write .prof stats to this path (canonical copy is auto-saved)",
    )
    p.add_argument("--top", type=int, default=30, help="Rows of profile output to print")
    p.add_argument(
        "--save",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Append a row to tests/benchmarks/results.jsonl (and save .prof)",
    )
    args = p.parse_args(argv)

    logging.getLogger("WebSearcher").setLevel(logging.WARNING)

    paths = args.fixtures or sorted(FIXTURES_DIR.glob("serps*.json.bz2"))
    if not paths:
        print(f"No fixtures found in {FIXTURES_DIR}")
        sys.exit(1)

    # Record the interpreter: timings are only comparable within one Python build.
    print(
        f"Python {platform.python_version()} "
        f"({platform.python_implementation()}, {sys.platform}) | WebSearcher {ws.__version__}"
    )

    records = load_records(paths, args.limit or None)
    htmls = [r["html"] for r in records]
    print(f"Loaded {len(htmls)} SERPs from {len(paths)} fixture(s):")
    for path in paths:
        print(f"  {path.name}")

    # Warm up imports, caches, and the parser code paths (untimed).
    for html in htmls:
        ws.parse_serp(html)

    meta = run_metadata(paths, len(htmls), args.iterations)

    if args.profile:
        run_profile(
            htmls, args.iterations, args.profile_sort, args.profile_out, args.top, meta, args.save
        )
    else:
        run_benchmark(htmls, args.iterations, args.runs, meta, args.save)


if __name__ == "__main__":
    main()
