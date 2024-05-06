""" Test search and parse multiple queries from file
"""

import os
import time
import pandas as pd
import WebSearcher as ws

# Filepaths
data_dir = os.path.join("data", f"demo-ws-v{ws.__version__}")
fp_serps = os.path.join(data_dir, 'serps.json')
fp_results = os.path.join(data_dir, 'results.json')
dir_html = os.path.join(data_dir, 'html')
os.makedirs(dir_html, exist_ok=True)

# Load query list from file, from: https://ahrefs.com/blog/top-google-searches/
fp_queries = 'data/tests/top_searches_google_2020-04.tsv'
top_list = pd.read_csv(fp_queries, sep='\t')
queries = top_list['keyword']

# Search, parse, and save
for qry in queries:
    se = ws.SearchEngine()                  # Initialize searcher
    se.search(qry)                          # Conduct Search
    se.parse_results()                      # Parse Results
    se.save_serp(append_to=fp_serps)        # Save SERP to json (html + metadata)
    se.save_results(append_to=fp_results)   # Save results to json
    se.save_serp(save_dir=dir_html)         # Save SERP html to dir (no metadata)
    time.sleep(30)                            # Wait 30 seconds
