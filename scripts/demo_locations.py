"""Download and use locations"""

from pathlib import Path

import polars as pl

import WebSearcher as ws

# Retrieve and save latest location data
data_dir = Path("data/google_locations")
data_dir.mkdir(parents=True, exist_ok=True)
ws.download_locations(str(data_dir))

# Read it back in
f = sorted(data_dir.iterdir())[-1]  # Last file
locs = pl.read_csv(f)

# locs.schema
#
# Schema([('Criteria ID', Int64),
#         ('Name', String),
#         ('Canonical Name', String),
#         ('Parent ID', Int64),
#         ('Country Code', String),
#         ('Target Type', String),
#         ('Status', String)])

# locs.row(0, named=True)
#
# {'Criteria ID': 1000002,
#  'Name': 'Kabul',
#  'Canonical Name': 'Kabul,Kabul,Afghanistan',
#  'Parent ID': 9075394,
#  'Country Code': 'AF',
#  'Target Type': 'City',
#  'Status': 'Active'}

# Looking for Canonical Names

## Filter
regex = r"(?=.*Boston)(?=.*Massachusetts)"  # Has Boston and Massachusetts
matches = locs.filter(pl.col("Canonical Name").str.contains(regex))
print(matches.select("Canonical Name"))
# 15849                                Boston,Massachusetts,United States
# 15908                           East Boston,Massachusetts,United States
# 66033    Boston Logan International Airport,Massachusetts,United States
# 84817                        Boston College,Massachusetts,United States
# 85985                          South Boston,Massachusetts,United States


# Set Canonical Name
canon_name = "Boston,Massachusetts,United States"

# Get corresponding row
name = locs.filter(pl.col("Canonical Name") == canon_name).row(0, named=True)
print(name)

# {'Criteria ID': 1018127,
#  'Name': 'Boston',
#  'Canonical Name': 'Boston,Massachusetts,United States',
#  'Parent ID': 21152,
#  'Country Code': 'US',
#  'Target Type': 'City',
#  'Status': 'Active'}


# Initialize crawler
se = ws.SearchEngine()

# Conduct Search
qry = "pizza"
se.search(qry, location=canon_name)

# Parse Results
se.parse_results()

# Print results
if se.results:
    df = pl.DataFrame(se.results)
    with pl.Config(fmt_str_lengths=80):
        print(df.select("type", "title"))

#             type                                                        title
#    local_results                                FLORINA Pizzeria & Paninoteca
#    local_results                                              Regina Pizzeria
#    local_results                                       Halftime King of Pizza
#          general                   Where to Eat Excellent Pizza Around Boston
#          general             Where to Find the Best Pizza in Boston Right Now
#          general  Pizza Hut | Delivery & Carryout - No One OutPizzas The Hut!
#          general   Domino's: Pizza Delivery & Carryout, Pasta, Chicken & More
#  people_also_ask                                                         None
#          general            THE 10 BEST Pizza Places in Boston (Updated 2024)
#          general  20 Best Pizza Spots in Boston For Delicious Slices And Pies
#          general               Supreme Pizza - Pizza Restaurant in Boston, MA
#          general                 Best Pizza in Boston: 27 Famous Pizza Places
#          general                        New Market Pizza - Boston, Boston, MA
#          general   Home | Regina Pizzeria, Boston's Brick Oven Pizza - Boston
# searches_related                                                         None
#        knowledge

dir_html = Path("data/html")
dir_html.mkdir(parents=True, exist_ok=True)
se.save_search(append_to=str(dir_html / "searches.json"))
se.save_serp(save_dir=str(dir_html))
