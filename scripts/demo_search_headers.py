"""Test search and parse a single query from command line"""

import argparse
from pathlib import Path

import WebSearcher as ws

MODIFIED_HEADERS = {
    "Host": "www.google.com",
    "Referer": "https://www.google.com/",
    "Accept": "*/*",
    "Accept-Encoding": "gzip,deflate,br",
    "Accept-Language": "en-US,en;q=0.5",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0",
}

# Settings
parser = argparse.ArgumentParser()
parser.add_argument("-q", "--query", type=str, help="A search query", required=True)
parser.add_argument(
    "-d",
    "--data_dir",
    type=str,
    help="Directory to save data",
    default=str(Path("data") / f"demo-ws-v{ws.__version__}"),
)
args = parser.parse_args()
print(f"WebSearcher v{ws.__version__} | Search Query: {args.query} | Output: {args.data_dir}")

# Filepaths
data_path = Path(args.data_dir)
fp_serps = data_path / "serps.json"
fp_results = data_path / "results.json"
dir_html = data_path / "html"
dir_html.mkdir(parents=True, exist_ok=True)

# Search, parse, and save
se = ws.SearchEngine(headers=MODIFIED_HEADERS)  # Initialize searcher
se.search(args.query)  # Conduct Search
se.parse_results()  # Parse Results
se.save_serp(append_to=fp_serps)  # Save SERP to json (html + metadata)
se.save_results(append_to=fp_results)  # Save results to json
se.save_serp(save_dir=dir_html)  # Save SERP html to dir (no metadata)
