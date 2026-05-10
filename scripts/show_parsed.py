"""Show the parsed-results table for a saved SERP."""

import json
from pathlib import Path

import polars as pl
import typer
from wcwidth import wcswidth

import WebSearcher as ws

DEFAULT_DATA_DIR = str(Path("data") / f"demo-ws-v{ws.__version__}")

app = typer.Typer()


def trunc(s, n: int = 55) -> str:
    """Truncate and pad `s` to exactly `n` terminal cells, accounting for wide chars."""
    if s is None:
        return "-".ljust(n)
    s = str(s).replace("\n", " ")
    out = ""
    width = 0
    for ch in s:
        w = wcswidth(ch)
        if w < 0:
            continue  # control char
        if width + w > n - 1:
            out += "…"
            width += 1
            break
        out += ch
        width += w
    return out + " " * (n - width)


def show(s):
    return "-" if s is None else s


def details_summary(d: dict | None) -> str:
    if not d:
        return "-"
    t = d.get("type", "?")
    if "items" in d:
        return f"{t} (n={len(d.get('items') or [])})"
    if t == "ratings":
        return f"ratings {d.get('rating')}/{d.get('scale')} ({d.get('n_reviews')})"
    if t == "place":
        parts = []
        if d.get("rating") is not None:
            parts.append(f"{d['rating']}({d.get('n_reviews')})")
        elif d.get("n_reviews") == 0:
            parts.append("no reviews")
        if d.get("price"):
            parts.append(d["price"])
        if d.get("category"):
            parts.append(d["category"])
        return "place " + " · ".join(parts) if parts else "place"
    if t == "video":
        bits = [v for v in (d.get("source"), d.get("duration")) if v]
        return "video" + (f" {' · '.join(bits)}" if bits else "")
    return t


@app.command()
def main(
    query: str = typer.Argument(None, help="Query whose saved SERP to parse and display"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Directory containing serps.json"),
    list_queries: bool = typer.Option(False, "--list", help="List available queries and exit"),
    width: int = typer.Option(500, help="Table width in characters"),
) -> None:
    fp = Path(data_dir) / "serps.json"
    if not fp.exists():
        typer.echo(f"Not found: {fp}")
        raise typer.Exit(1)

    queries: list[str] = []
    html: str | None = None
    with open(fp) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            qry = rec.get("qry")
            queries.append(qry)
            if query and qry == query:
                html = rec.get("html")

    if list_queries or not query:
        for q in queries:
            typer.echo(q)
        raise typer.Exit(0)

    if html is None:
        typer.echo(f"No SERP found for query {query!r}. Use --list to see available queries.")
        raise typer.Exit(1)

    parsed = ws.parse_serp(html)
    results = parsed.get("results") or []

    pl.Config.set_tbl_rows(max(len(results), 50))
    pl.Config.set_tbl_width_chars(width)
    pl.Config.set_fmt_str_lengths(200)
    pl.Config.set_tbl_hide_dataframe_shape(True)
    pl.Config.set_tbl_hide_column_data_types(True)

    df = pl.DataFrame(
        [
            {
                "rank": r.get("cmpt_rank"),
                "sub": r.get("sub_rank"),
                "sec": r.get("section"),
                "type": r.get("type"),
                "sub_type": show(r.get("sub_type")),
                "title": trunc(r.get("title")),
                "url": show(r.get("url")),
                "details": details_summary(r.get("details")),
            }
            for r in results
        ]
    )

    typer.echo(f"qry={query!r}, components={len(results)}\n")
    typer.echo(str(df))


if __name__ == "__main__":
    app()
