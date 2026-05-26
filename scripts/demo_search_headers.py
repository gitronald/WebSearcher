"""Search and parse a single query using modified request headers."""

from pathlib import Path

import polars as pl
import typer

import WebSearcher as ws

MODIFIED_HEADERS = {
    "Host": "www.google.com",
    "Referer": "https://www.google.com/",
    "Accept": "*/*",
    "Accept-Encoding": "gzip,deflate,br",
    "Accept-Language": "en-US,en;q=0.5",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0",
}

DEFAULT_DATA_DIR = str(Path("data") / f"demo-ws-v{ws.__version__}")

app = typer.Typer()


@app.command()
def main(
    query: str = typer.Argument(..., help="Search query to use"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Directory to save data"),
) -> None:
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    fps = {k: data_path / f"{k}.json" for k in ["serps", "parsed"]}
    print(f"WebSearcher v{ws.__version__} | Search Query: {query} | Output: {data_dir}")

    # Search with the requests method and custom headers
    se = ws.SearchEngine(method="requests", requests_config={"headers": MODIFIED_HEADERS})
    se.search(query)  # Conduct search
    se.parse_serp()  # Parse results
    se.save_serp(append_to=fps["serps"])  # Save SERP to json (html + metadata)
    se.save_parsed(append_to=fps["parsed"])  # Save parsed results/features to json

    if se.parsed.results:
        df = pl.DataFrame(se.parsed.results)
        print(df.select("type", "sub_type", "title", "url"))


if __name__ == "__main__":
    app()
