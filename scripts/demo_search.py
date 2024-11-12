""" Test search and parse a single query from command line
"""

import os
import argparse
import pandas as pd
import WebSearcher as ws

pd.set_option('display.width', 120, 
              'display.max_rows', None, 
              'display.max_columns', None,
              'display.max_colwidth', 40)

def main():
    # Settings
    parser = argparse.ArgumentParser()
    parser.add_argument("-q", "--query", type=str, help="A search query", required=True)
    parser.add_argument("-d", "--data_dir", type=str, help="Directory to save data", 
                        default=os.path.join("data", f"demo-ws-v{ws.__version__}"))
    args = parser.parse_args()
    print(f'WebSearcher v{ws.__version__}\nSearch Query: {args.query}\nOutput Dir: {args.data_dir}\n')

    # Filepaths
    fp_serps = os.path.join(args.data_dir, 'serps.json')
    fp_results = os.path.join(args.data_dir, 'results.json')
    fp_searches = os.path.join(args.data_dir, 'searches.json')
    dir_html = os.path.join(args.data_dir, 'html')
    os.makedirs(dir_html, exist_ok=True)

    # Search, parse, and save
    se = ws.SearchEngine()                  # Initialize searcher
    se.search(args.query)                   # Conduct Search
    se.parse_results()                      # Parse Results
    se.save_serp(append_to=fp_serps)        # Save SERP to json (html + metadata)
    se.save_results(append_to=fp_results)   # Save results to json
    se.save_serp(save_dir=dir_html)         # Save SERP html to dir (no metadata)
    se.save_search(append_to=fp_searches)   # Save search metadata + extracted features

    # Convert results to dataframe and print select columns
    results = pd.DataFrame(se.results)
    print(results[['type', 'title', 'url']])

if __name__ == "__main__":
    main()