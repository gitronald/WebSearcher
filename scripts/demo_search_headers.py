""" Test search and parse a single query from command line
"""

import argparse
import pandas as pd
import WebSearcher as ws

parser = argparse.ArgumentParser()
parser.add_argument("-q", "--query", type=str, help="A search query")
args = parser.parse_args()

MODIFIED_HEADERS = {
    'Host': 'www.google.com',
    'Referer': 'https://www.google.com/',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip,deflate,br',
    'Accept-Language': 'en-US,en;q=0.5',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0',
}

if not args.query:
    print('Must include -q arg')
else:
    print(f'WebSearcher v{ws.__version__} | Search Query: {args.query}')
    
    # Initialize crawler
    se = ws.SearchEngine(headers=MODIFIED_HEADERS)
    
    # Conduct Search
    se.search(args.query)

    # Parse Results
    se.parse_results()

    # Shape as dataframe
    results = pd.DataFrame(se.results)
    print(results.head())

    try:
        se.save_serp(append_to='test_serp_save.json')
        se.save_results(append_to='test_results_save.json')
        se.save_serp(save_dir=".")
    except Exception as e:
        print('Save error', e)
