"""Convert a parsed.json file to a results CSV

Reads a parsed JSONL file (one SERP per line with nested results),
flattens each result into a row with serp_id and version columns,
and writes to CSV.

Usage:
    uv run python scripts/parsed_to_csv.py data/demo-ws-v0.6.8a0/parsed.json
    uv run python scripts/parsed_to_csv.py data/demo-ws-v0.6.8a0/parsed.json -o results.csv
"""

import argparse
from pathlib import Path

import orjson
import polars as pl


def read_parsed_jsonl(filepath: str) -> pl.DataFrame:
    """Read parsed JSONL and flatten results into rows"""
    rows = []
    with open(filepath) as f:
        for line in f:
            record = orjson.loads(line)
            serp_id = record["serp_id"]
            version = record.get("version", "")
            for result in record.get("results", []):
                result["serp_id"] = serp_id
                result["version"] = version
                # Serialize details to JSON string (mixed types: dict, list, null)
                if result.get("details") is not None:
                    result["details"] = orjson.dumps(result["details"]).decode()
                rows.append(result)
    return pl.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("filepath", help="Path to parsed.json file")
    parser.add_argument("-o", "--output", help="Output CSV path (default: <input_dir>/results.csv)")
    args = parser.parse_args()

    filepath = Path(args.filepath)
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        raise SystemExit(1)

    df = read_parsed_jsonl(str(filepath))

    # Reorder columns: identifiers first, then result fields
    id_cols = ["serp_id", "version"]
    result_cols = [c for c in df.columns if c not in id_cols]
    df = df.select(id_cols + result_cols)

    output = Path(args.output) if args.output else filepath.parent / "results.csv"
    df.write_csv(output)
    print(f"{len(df)} results from {df['serp_id'].n_unique()} SERPs -> {output}")


if __name__ == "__main__":
    main()
