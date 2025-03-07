""" Download and use locations
"""
import os
import pandas as pd
import WebSearcher as ws

# Retrieve and save latest location data 
data_dir = 'data/google_locations'
os.makedirs(data_dir, exist_ok=True)
ws.download_locations(data_dir)

# Read it back in
f  = os.listdir(data_dir)[-1]  # Last file
fp = os.path.join(data_dir, f) # File path
locs = pd.read_csv(fp)         # Read

# locs.info()
#
# <class 'pandas.core.frame.DataFrame'>
# RangeIndex: 102029 entries, 0 to 102028
# Data columns (total 7 columns):
# Criteria ID       102029 non-null int64
# Name              102029 non-null object
# Canonical Name    102029 non-null object
# Parent ID         101788 non-null float64
# Country Code      102013 non-null object
# Target Type       102029 non-null object
# Status            102029 non-null object
# dtypes: float64(1), int64(1), object(5)
# memory usage: 5.4+ MB

# locs.iloc[0]
#
# Criteria ID                       1000002
# Name                                Kabul
# Canonical Name    Kabul,Kabul,Afghanistan
# Parent ID                     9.07539e+06
# Country Code                           AF
# Target Type                          City
# Status                             Active
# Name: 0, dtype: object

# Looking for Canonical Names

## Masks
regex = r'(?=.*Boston)(?=.*Massachusetts)' # Has Boston and Massachusetts
str_mask = locs['Canonical Name'].str.contains(regex)

locs[str_mask]
# 5368                                      Boston,England,United Kingdom
# 15849                                Boston,Massachusetts,United States
# 15908                           East Boston,Massachusetts,United States
# 17201                                 New Boston,Michigan,United States
# 19636                            New Boston,New Hampshire,United States
# 24368                                    New Boston,Texas,United States
# 24763                                     Boston,Virginia,United States
# 25003                               South Boston,Virginia,United States
# 66033    Boston Logan International Airport,Massachusetts,United States
# 66181    Manchester-Boston Regional Airport,New Hampshire,United States
# 84817                        Boston College,Massachusetts,United States
# 85140                  Boston Ave - Mill Hill,Connecticut,United States
# 85985                          South Boston,Massachusetts,United States
# Name: Canonical Name, dtype: object


# Set Canonical Name
canon_name = 'Boston,Massachusetts,United States'

# Get corresponding row
name = locs[locs['Canonical Name'] == canon_name].iloc[0]
name

# Criteria ID                                  1018127
# Name                                          Boston
# Canonical Name    Boston,Massachusetts,United States
# Parent ID                                      21152
# Country Code                                      US
# Target Type                                     City
# Status                                        Active
# Name: 15849, dtype: object


# Initialize crawler
se = ws.SearchEngine()

# Conduct Search
qry = 'pizza'
se.search(qry, location=canon_name)

# Parse Results
se.parse_results()

# Shape as dataframe
if se.results:
    results = pd.DataFrame(se.results)
    with pd.option_context('display.max_colwidth', 80):
        print(results[['type', 'title']])

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

dir_html = os.path.join("data", 'html')
os.makedirs(dir_html, exist_ok=True)
se.save_search(append_to=os.path.join(dir_html, "searches.json"))
se.save_serp(save_dir=dir_html)
