""" Test search and parse multiple queries from file
"""

import os
import time
import pandas as pd
import WebSearcher as ws

# Filepaths
data_dir = f"ws-v{ws.__version__}-demo-data"
fp_serps = os.path.join(data_dir, 'serps.json')
fp_results = os.path.join(data_dir, 'results.json')
dir_html = os.path.join(data_dir, 'html')
os.makedirs(dir_html, exist_ok=True)

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