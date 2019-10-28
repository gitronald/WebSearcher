""" Test search and parse
"""

import argparse
import pandas as pd
import WebSearcher as ws

parser = argparse.ArgumentParser()
parser.add_argument("-q", "--query", type=str, help="A search query")
args = parser.parse_args()

if not args.query:
    print('Must include -q arg')
else:
    print(args.query)
    
    # Initialize crawler
    se = ws.SearchEngine()
    
    # Conduct Search
    se.search(args.query)

    # Parse Results
    se.parse_results()

    # Shape as dataframe
    results = pd.DataFrame(se.results)
    print(results.head())
