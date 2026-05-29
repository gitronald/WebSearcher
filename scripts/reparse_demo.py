"""Reparse the demo SERP corpus and emit parsed output as NDJSON.

The demo dirs under data/demo-ws-*/ hold real captured SERPs (serps.json) that are
NOT in tests/fixtures — a broader, version-diverse corpus for stress-testing the
parser on shapes the snapshot suite never covers. This script runs the full
parse_serp pipeline over every demo SERP and writes one {serp_id, qry, version,
features, results} record per line, so the SAME script can be run on two git
checkouts (e.g. the selectolax branch vs the pre-branch bs4 baseline) and the two
outputs diffed to catch regressions.

    uv run python scripts/reparse_demo.py --out /tmp/parsed_branch.ndjson
"""

import json
from pathlib import Path

import typer

import WebSearcher as ws

app = typer.Typer(add_completion=False)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@app.command()
def main(
    out: Path = typer.Option(..., "--out", help="Output NDJSON path"),
    glob: str = typer.Option("demo-ws-*/serps.json", help="Glob under data/ for serps files"),
    limit: int = typer.Option(0, help="Cap SERPs per file (0 = all)"),
):
    paths = sorted(DATA_DIR.glob(glob))
    if not paths:
        typer.echo(f"No serps files match {glob} under {DATA_DIR}")
        raise typer.Exit(1)

    n = 0
    errors = 0
    with open(out, "w") as fout:
        for path in paths:
            with open(path) as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    if limit and i >= limit:
                        break
                    rec = json.loads(line)
                    html = rec.get("html")
                    if not html:
                        continue
                    out_rec = {
                        "src": path.parent.name,
                        "serp_id": rec.get("serp_id"),
                        "qry": rec.get("qry"),
                        "version": rec.get("version"),
                    }
                    try:
                        parsed = ws.parse_serp(html)
                        out_rec["features"] = parsed.get("features")
                        out_rec["results"] = parsed.get("results")
                    except Exception as e:  # noqa: BLE001 — record, keep going
                        out_rec["error"] = f"{type(e).__name__}: {e}"
                        errors += 1
                    fout.write(json.dumps(out_rec, sort_keys=True, default=str) + "\n")
                    n += 1
    typer.echo(f"Wrote {n} parsed SERPs ({errors} errors) from {len(paths)} file(s) -> {out}")


if __name__ == "__main__":
    app()
