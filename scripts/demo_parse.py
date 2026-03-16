"""Test parse SERP from .html file"""

import argparse

import polars as pl

import WebSearcher as ws

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--filepath", help="The SERP html file")
args = parser.parse_args()

if not args.filepath:
    print("Must include -f arg")
else:
    soup = ws.load_soup(args.filepath)
    parsed = ws.parse_serp(soup)
    if parsed["results"]:
        df = pl.DataFrame(parsed["results"])
        print(df.select("type", "title", "url"))

    # Obtain HTML component list for examination
    cmpts = ws.Extractor(soup).extract_components()
