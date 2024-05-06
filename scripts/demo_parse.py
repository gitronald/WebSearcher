""" Test parse SERP from .html file
"""

import argparse
import pandas as pd
import WebSearcher as ws

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--filepath", help="The SERP html file")
args = parser.parse_args()

if not args.filepath:
    print('Must include -f arg')
else:
    soup = ws.load_soup(args.filepath)
    parsed = ws.parse_serp(soup)
    results = pd.DataFrame(parsed)
    print(results[['type', 'title', 'url']])

    # Obtain HTML component list for examination
    cmpts = ws.extract_components(soup)
