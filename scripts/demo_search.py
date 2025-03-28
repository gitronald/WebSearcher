""" Test search and parse a single query from command line
"""

import os
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
    query: str = typer.Argument("why is the sky blue?", help="Search query to use"),
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
    print(f'WebSearcher v{ws.__version__}\nSearch Query: {query}\nOutput Dir: {data_dir}\n')

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

    # Search and parse
    se.search(query, ai_expand=ai_expand)      # Conduct Search
    se.parse_results()                         # Parse Results
    se.save_serp(append_to=fps['serps'])       # Save SERP to json (html + metadata)
    se.save_search(append_to=fps['searches'])  # Save search metadata to json
    se.save_parsed(append_to=fps['parsed'])    # Save results/features to json

    # Convert results to dataframe and print select columns
    if se.parsed["results"]:
        results = pd.DataFrame(se.parsed["results"])
        print(results[['type', 'sub_type', 'title', 'url']])

if __name__ == "__main__":
    app()