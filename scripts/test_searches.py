""" Test search and parse multiple queries from file
"""

import os
import time
import datetime
import pandas as pd
import WebSearcher as ws

# Output filepaths
date = datetime.datetime.now().strftime('%Y-%m-%d')
dir_serps = f'data/tests/{date}/html'
fp_results = f'data/tests/{date}/results.json'
os.makedirs(dir_serps, exist_ok=True)

# Load query list from file, from: https://ahrefs.com/blog/top-google-searches/
fp_queries = 'data/tests/top_searches_google_2020-04.tsv'
top_list = pd.read_csv(fp_queries, sep='\t')
queries = top_list['keyword']

for qry in queries:
    se = ws.SearchEngine()                    # Initialize crawler
    se.search(qry)                            # Conduct search
    se.save_serp(save_dir=dir_serps)          # Save search as an HTML file
    se.parse_results()                        # Parse results
    se.save_results(append_to=fp_results)     # Save results to file
    time.sleep(30)                            # Wait 30 seconds 