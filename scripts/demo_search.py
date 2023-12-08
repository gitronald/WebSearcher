""" Test search and parse a single query from command line
"""

import os
import argparse
import pandas as pd
import WebSearcher as ws

parser = argparse.ArgumentParser()
parser.add_argument("-q", "--query", type=str, help="A search query")
args = parser.parse_args()

if not args.query:
    print('Must include -q arg'); exit();

# Settings
query = args.query
data_dir = f"ws-v{ws.__version__}-demo-data"

# Filepaths
fp_serps = os.path.join(data_dir, 'serps.json')
fp_results = os.path.join(data_dir, 'results.json')
dir_html = os.path.join(data_dir, 'html')
os.makedirs(dir_html, exist_ok=True)

# Collect and parse
se = ws.SearchEngine()   # Initialize crawler
se.search(query)         # Conduct Search
se.parse_results()       # Parse Results

# Save SERP and result details
se.save_serp(append_to=fp_serps)
se.save_results(append_to=fp_results)
se.save_serp(save_dir=dir_html)

# Convert results to dataframe
results = pd.DataFrame(se.results)
print(results.head())