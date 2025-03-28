""" Test search and parse multiple queries from file
"""

import os
import time
import typer
import pandas as pd
import WebSearcher as ws

pd.set_option('display.width', 160, 
              'display.max_rows', None, 
              'display.max_columns', None,
              'display.max_colwidth', 40)

DEFAULT_DATA_DIR = os.path.join("data", f"demo-ws-v{ws.__version__}")

app = typer.Typer()

@app.command()
def main(
    method: str = typer.Argument("selenium", help="Search method to use: 'selenium' or 'requests'"),
    data_dir: str = typer.Option(DEFAULT_DATA_DIR, help="Prefix for output files"),
    headless: bool = typer.Option(False, help="Run browser in headless mode"),
    use_subprocess: bool = typer.Option(False, help="Run browser in a separate subprocess"),
    version_main: int = typer.Option(133, help="Main version of Chrome to use"),
    ai_expand: bool = typer.Option(True, help="Expand AI overviews if present"),
    driver_executable_path: str = typer.Option("", help="Path to ChromeDriver executable"),
) -> None:

    # Filepaths
    fps = {k: os.path.join(data_dir, f"{k}.json") for k in ["serps", "parsed", "searches"]}
    os.makedirs(data_dir, exist_ok=True)

    # Load query list from file, from: https://ahrefs.com/blog/top-google-searches/
    fp_queries = 'data/tests/top_searches_google_2020-04.tsv'
    top_list = pd.read_csv(fp_queries, sep='\t')
    queries = top_list['keyword']

    for qry in queries:

        # Setup search engine
        se = ws.SearchEngine(
            method=method, 
            selenium_config={
                "headless": headless,
                "use_subprocess": use_subprocess,
                "driver_executable_path": driver_executable_path,
                "version_main": version_main,
            }
        )

        # Search, parse, and save
        se.search(qry, ai_expand=ai_expand)       # Conduct Search
        se.parse_results()                        # Parse Results
        se.save_serp(append_to=fps['serps'])      # Save SERP to json (html + metadata)
        se.save_search(append_to=fps['searches']) # Save search to json (metadata only)
        se.save_parsed(append_to=fps['parsed'])   # Save parsed results and SERP features to json

        # Convert results to dataframe and print select columns
        if se.parsed["results"]:
            results = pd.DataFrame(se.parsed["results"])
            print(results[['type', 'sub_type', 'title', 'url']])

        time.sleep(30)
