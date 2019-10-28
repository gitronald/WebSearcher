# WebSearcher 0.1.12  
## Tools for conducting, collecting, and parsing web search  
[![PyPI version](https://badge.fury.io/py/WebSearcher.svg)](https://badge.fury.io/py/WebSearcher)

This package provides tools for conducting algorithm audits of web search and includes a scraper with tools for geolocating, conducting, and saving searches. It also includes a modular parser for decomposing a SERP into list of components with categorical classifications and position-based specifications.

## Table of Contents

- [Getting Started](#getting-started)
- [Usage](#usage)
    * [Prepare a search](#prepare-a-search)
    * [Conduct a search](#conduct-a-search)
    * [Save a search](#save-a-search)
- [Localization](#localization)
    + [Obtain location names](#obtain-location-names)
    + [Conduct a localized search](#conduct-a-localized-search)
- [Contributing](#contributing)
    + [Repair or Enhance a Parser](#repair-or-enhance-a-parser)
    + [Add a Parser](#add-a-parser)
- [Similar Packages](#similar-packages)
- [License](#license)

---  
## Getting Started

pip version [link](https://pypi.org/project/WebSearcher)
```bash
pip install WebSearcher
```

Github version
```bash
git clone https://github.com/github/gitronald/WebSearcher.git
pip install ./WebSearcher
```

---  
## Usage

#### Prepare a search
```python
import WebSearcher as ws

# Initialize crawler with defaults (headers, logs, ssh tunnels)
se = ws.SearchEngine()

```
```python
vars(se)

{'url': 'https://www.google.com/search',
 'params': {},
 'headers': {'Host': 'www.google.com',
  'Referer': 'https://www.google.com/',
  'Accept': '*/*',
  'Accept-Language': 'en-US,en;q=0.5',
  'Accept-Encoding': 'gzip,deflate,br',
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0'},
 'ssh_tunnel': None,
 'sesh': <requests.sessions.Session at 0x7f7bad8efba8>,
 'log': <Logger WebSearcher.searchers (DEBUG)>,
 'html': None,
 'results': [],
 'results_html': []}
```

#### Conduct a search

```python
# Conduct Search
se.search('immigration')
```
```
2019-08-14 01:25:38,267 | 2688 | INFO | WebSearcher.searchers | 200 | Searching immigration
```

```python
# Parse Results
se.parse_results()
```
```
2019-08-14 01:25:42,112 | 2688 | INFO | WebSearcher.searchers | Not brotli compressed
2019-08-14 01:25:42,208 | 2688 | INFO | WebSearcher.parsers | Parsing SERP 4d4fe27fe6b6466041e326622719b03ccc6542427c577c69740ae7fc
```

```python
se.results[0]
{'cite': 'The New York Times',
 'cmpt_rank': 0,
 'details': {'img_url': None, 'live_stamp': False, 'orient': 'h'},
 'lang': 'en',
 'qry': 'immigration',
 'serp_id': '4d4fe27fe6b6466041e326622719b03ccc6542427c577c69740ae7fc',
 'serp_rank': 0,
 'sub_rank': 0,
 'timestamp': '1 day ago',
 'title': 'Trump Policy Favors Wealthier Immigrants for Green Cards',
 'type': 'top_stories',
 'url': 'https://www.nytimes.com/2019/08/12/us/politics/trump-immigration-policy.html'}
```

### Save a Search

Recommended: Append html and meta data as lines to a json file. 
Useful for larger or ongoing crawls.

```python
se.save_serp(append_to='serps.json')
```

Alternative: Save individual html files in a directory, named by a provided or (default) generated `serp_id`. Useful for smaller qualitative explorations where you want to quickly look at what is showing up. No meta data is saved, but timestamps could be recovered from the files themselves.

```python
se.save_serp(save_dir='./serps')
```

---  
## Localization

Conduct web searches from a location of choice.

#### Obtain location names

To conduct localized searches, you only need one additional data point: The __"Canonical Name"__ of each location.   
These are available online, and can be downloaded using a built in function that checks for the most recent version. 

```python
# Set save location  
data_dir = './location_data'

# Download latest data; checks for local version before downloading
ws.download_locations(data_dir)

f  = os.listdir(data_dir)[-1]  # Last file
fp = os.path.join(data_dir, f) # File path
locs = pd.read_csv(fp)         # Read
locs.info()
```
```
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 102029 entries, 0 to 102028
Data columns (total 7 columns):
Criteria ID       102029 non-null int64
Name              102029 non-null object
Canonical Name    102029 non-null object
Parent ID         101788 non-null float64
Country Code      102013 non-null object
Target Type       102029 non-null object
Status            102029 non-null object
dtypes: float64(1), int64(1), object(5)
memory usage: 5.4+ MB
```
```python
# Take a look at the first row
locs.iloc[0]
```
```
Criteria ID                       1000002
Name                                Kabul
Canonical Name    Kabul,Kabul,Afghanistan
Parent ID                     9.07539e+06
Country Code                           AF
Target Type                          City
Status                             Active
Name: 0, dtype: object
```

__Looking for Canonical Names__. In order to search from a given location, you must find the corresponding canonical name.

```python
# Filter for names containing "Boston" and "Massachusetts"
regex = r'(?=.*Boston)(?=.*Massachusetts)' 
str_mask = locs['Canonical Name'].str.contains(regex)
locs[str_mask]
```
```
15849                                Boston,Massachusetts,United States
15908                           East Boston,Massachusetts,United States
66033    Boston Logan International Airport,Massachusetts,United States
84817                        Boston College,Massachusetts,United States
85985                          South Boston,Massachusetts,United States
Name: Canonical Name, dtype: object
```

#### Conduct a localized search

After picking one, say `'Boston,Massachusetts,United States'`, you just add this to your `se.search()` call:

```python
# Conduct Search
qry = 'pizza'
loc = 'Boston,Massachusetts,United States'
se.search(qry, location=loc)

# Parse Results
se.parse_results()

# Shape as dataframe
results = pd.DataFrame(se.results)

# Show details of local results returned 
results[results.type=='local_results']['details'].tolist()
```

```
[{
    'rating': 4.0,
    'n_reviews': 152,
    'sub_type': 'Pizza',
    'contact': '226 N Market St'
},
{
    'rating': 4.6,
    'n_reviews': 752,
    'sub_type': 'Pizza',
    'contact': '69 Salem St'
},
{
    'sub_type': 'Pizza', 
    'contact': 'McCormack Building, 1 Ashburton Pl'
}]
```

---
## Contributing

Happy to have help! If you see a component that we aren't covering yet, please add it using the process below. If you have other improvements, feel free to add them any way you can.

Recently added:  
    - Location.

Coming next:  
    - Functions for using multiprocessing to parse SERPs.  
    - SSH tunneling

To do:  
    - SQL storage

### Repair or Enhance a Parser

1. Examine parser names in `/component_parsers/__init__.py`
2. Find parser file as `/component_parsers/{cmpt_name}.py`.

### Add a Parser

1. Add classifier to `component_classifier.py`, as `'cmpt_name'`
2. Add parser file in `/component_parsers` as `cmpt_name.py`, with function `parse_cmpt_name`.
3. Add import for `parse_cmpt_name` in `/component_parsers/__init__.py`

---  
## Similar Packages

Many other methods for scraping web search in python exist, but many of these projects have been abandoned, and I was not able to find one that provided details on the components (e.g. "Answer Boxes" and "Top Stories") and positioning configurations (e.g. a horizontally or vertically oriented carousel) that compose a modern SERP.

Some of the other projects are still ongoing and very interesting in their own ways. Arranged by increasing URL length. Feel free to add to the list through a pull request if you are aware of others:

- https://github.com/jarun/googler
- http://googolplex.sourceforge.net
- https://github.com/Jayin/google.py
- https://github.com/ecoron/SerpScrap
- https://github.com/henux/cli-google
- https://github.com/Kaiz0r/netcrawler
- https://github.com/NikolaiT/se-scraper
- https://github.com/nabehide/WebSearch
- https://github.com/rrwen/search_google
- https://github.com/howie6879/magic_google
- https://github.com/rohithpr/py-web-search
- https://github.com/MarioVilas/googlesearch
- https://github.com/aviaryan/python-gsearch
- https://github.com/nickmvincent/you-geo-see
- https://github.com/anthonyhseb/googlesearch
- https://github.com/KokocGroup/google-parser
- https://github.com/vijayant123/google-scrap
- https://github.com/BirdAPI/Google-Search-API
- http://googlesystem.blogspot.com/2008/04/google-search-rest-api.html

---  
## License

Copyright (C) 2017-2019 Ronald E. Robertson <rer@ronalderobertson.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
