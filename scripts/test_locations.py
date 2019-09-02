""" Download and use locations
"""
import os
import pandas as pd
import WebSearcher as ws

# Retrieve and save latest location data 
data_dir = './location_data'
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
results = pd.DataFrame(se.results)
print(results.head())

results[results.type=='local_results']['details'].tolist()

# [{
#     'rating': 4.0,
#     'n_reviews': 152,
#     'sub_type': 'Pizza',
#     'contact': '226 N Market St'
# },
# {
#     'rating': 4.6,
#     'n_reviews': 752,
#     'sub_type': 'Pizza',
#     'contact': '69 Salem St'
# },
# {
#     'sub_type': 'Pizza', 
#     'contact': 'McCormack Building, 1 Ashburton Pl'
# }]