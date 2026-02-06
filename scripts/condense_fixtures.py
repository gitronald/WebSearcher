"""Condense prerelease demo data into a single bz2-compressed test fixture"""

import bz2

import orjson
import typer

app = typer.Typer()


@app.command()
def main(
    version: str = typer.Argument(..., help="Version to condense (e.g. 0.6.7)"),
    data_dir: str = typer.Option("data", help="Directory containing demo data"),
    output_dir: str = typer.Option("tests/fixtures", help="Output directory for fixture"),
):
    """Combine prerelease demo SERPs into a bz2-compressed JSONL fixture.

    Globs data/demo-ws-v{version}*/serps.json, deduplicates by serp_id,
    and writes tests/fixtures/serps-v{version}.json.bz2.
    """
    from pathlib import Path

    # Collect records from all prerelease directories
    pattern = f"demo-ws-v{version}*"
    data_path = Path(data_dir)
    all_records: dict[str, dict] = {}
    total = 0

    for d in sorted(data_path.glob(pattern)):
        fp = d / "serps.json"
        if not fp.exists():
            continue
        with open(fp) as f:
            for line in f:
                r = orjson.loads(line)
                all_records[r["serp_id"]] = r
                total += 1
        print(f"  {d.name}: {sum(1 for _ in open(fp))} records")

    if not all_records:
        print(f"No data found matching {data_path / pattern}")
        raise typer.Exit(1)

    # Write compressed fixture
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    out_file = out_path / f"serps-v{version}.json.bz2"

    with bz2.open(out_file, "wb") as f:
        for r in all_records.values():
            f.write(orjson.dumps(r) + b"\n")

    size_mb = out_file.stat().st_size / 1024 / 1024
    print(f"\n  total: {total} records, {len(all_records)} unique")
    print(f"  wrote: {out_file} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    app()
