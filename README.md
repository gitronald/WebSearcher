# WebSearcher
## Tools for conducting and parsing web searches  
[![PyPI version](https://badge.fury.io/py/WebSearcher.svg)](https://badge.fury.io/py/WebSearcher)

This package provides tools for conducting algorithm audits of web search and 
includes a scraper built on `selenium` with tools for geolocating, conducting, 
and saving searches. It also includes a modular parser built on `BeautifulSoup` 
for decomposing a SERP into list of components with categorical classifications 
and position-based specifications. 

## Recent Changes

- `0.7.0`: Breaking changes, standardized data models on Pydantic, typed `details` field, and removed `DetailsItem`/`DetailsList`

See [CHANGELOG.md](CHANGELOG.md) for a longer history of changes by version.

## Table of Contents

- [WebSearcher](#websearcher)
  - [Tools for conducting and parsing web searches](#tools-for-conducting-and-parsing-web-searches)
  - [Recent Changes](#recent-changes)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
  - [Usage](#usage)
    - [Example Search Script](#example-search-script)
    - [Step by Step](#step-by-step)
      - [1. Initialize Collector](#1-initialize-collector)
      - [2. Conduct a Search](#2-conduct-a-search)
      - [3. Parse Search Results](#3-parse-search-results)
      - [4. Save HTML and Metadata](#4-save-html-and-metadata)
      - [5. Save Parsed Results](#5-save-parsed-results)
  - [Localization](#localization)
  - [Contributing](#contributing)
    - [Repair or Enhance a Parser](#repair-or-enhance-a-parser)
    - [Add a Parser](#add-a-parser)
    - [Testing](#testing)
    - [Test Fixtures](#test-fixtures)
  - [GitHub Actions](#github-actions)
  - [Similar Packages](#similar-packages)
  - [License](#license)

---
## Getting Started

```bash
# Install from PyPI
pip install WebSearcher

# Or install with uv
uv add WebSearcher

# Install development version from GitHub
pip install git+https://github.com/gitronald/WebSearcher@dev
```

---  
## Usage

### Example Search Script

There's an example search script that can be run from the command line with uv with a search query argument (`-q` or `--query`).

```bash
uv run demo-search -q "election news"
```

Search results are constantly changing, especially for news, but just now (see timestamp below), that search returned the following details (only a subset of columns are shown):

```
WebSearcher v0.4.2.dev0
Search Query: election news
Output Dir: data/demo-ws-v0.4.2.dev0

2024-11-11 10:55:27.362 | INFO | WebSearcher.searchers | 200 | election news

                type                                    title                                      url
0        top_stories  There’s a Lot of Fighting Over Why H...  https://slate.com/news-and-politics/...
1        top_stories  Dearborn’s Arab Americans feel vindi...  https://www.politico.com/news/2024/1...
2        top_stories  Former Kamala Harris aide says Joe B...  https://www.usatoday.com/story/news/...
3        top_stories  Election live updates: Control of Co...  https://apnews.com/live/house-senate...
4        top_stories  Undecided races of the 2024 election...  https://abcnews.go.com/538/live-upda...
5         local_news  These Southern California House race...  https://www.nbclosangeles.com/decisi...
6         local_news  Election Day is over in California. ...  https://www.sacbee.com/news/politics...
7         local_news  Why Haven’t Numerous California Hous...  https://www.democracydocket.com/news...
8         local_news  Anti-slavery measure Prop. 6 fails, ...  https://calmatters.org/politics/elec...
9            general  November 10, 2024, election and Trum...  https://www.cnn.com/politics/live-ne...
10           general  When do states have to certify 2024 ...  https://www.cbsnews.com/news/state-e...
11           general  US Election 2024 | Latest News & Ana...  https://www.bbc.com/news/topics/cj3e...
12           unknown                                     None                                     None
13           general                            2024 Election  https://www.npr.org/sections/elections/
14           general  Politics, Policy, Political News - P...                https://www.politico.com/
15           general  Presidential election highlights: No...  https://apnews.com/live/trump-harris...
16           general  Election 2024: Latest News, Top Stor...  https://calmatters.org/category/poli...
17  searches_related                                     None                                     None
```

By default, that script will save the outputs to a directory (`data/demo-ws-{version}/`) with the structure below. Within that, the script saves the HTML both to a single JSON lines file (`serps.json`), which is recommended because it includes metadata about the search, and to individual HTML files in a subdirectory (`html/`) for ease of viewing the SERPs (e.g., in a browser). The script also saves the parsed search results to a JSON file (`results.json`).

```sh
ls -hal data/demo-ws-v0.4.2.dev0/
```
```
total 1020K
drwxr-xr-x 3 user user 4.0K 2024-11-11 10:54 ./
drwxr-xr-x 8 user user 4.0K 2024-11-11 10:54 ../
drwxr-xr-x 2 user user 4.0K 2024-11-11 10:55 html/
-rw-r--r-- 1 user user  16K 2024-11-11 10:55 results.json
-rw-r--r-- 1 user user 990K 2024-11-11 10:55 serps.json
```

### Step by Step 

Example search and parse pipeline (via requests):

```python
import WebSearcher as ws
se = ws.SearchEngine()                     # 1. Initialize collector
se.search('immigration news')              # 2. Conduct a search
se.parse_serp()                            # 3. Parse search results
se.save_serp(append_to='serps.json')       # 4. Save HTML and metadata
se.save_results(append_to='results.json')  # 5. Save parsed results

```

#### 1. Initialize Collector

```python
import WebSearcher as ws

# Initialize collector with method and other settings
se = ws.SearchEngine(
    method="selenium", 
    selenium_config = {
        "headless": False,
        "use_subprocess": False,
        "driver_executable_path": "",
        "version_main": 141,
    }
)
```   

#### 2. Conduct a Search

```python
se.search('immigration news')
# 2024-08-19 14:09:18.502 | INFO | WebSearcher.searchers | 200 | immigration news
```

#### 3. Parse Search Results

The example below is primarily for parsing search results as you collect HTML.
See `ws.parse_serp(html)` for parsing existing HTML data.

```python
se.parse_serp()

# Show first result
se.parsed.results[0]
{'section': 'main',
 'cmpt_rank': 0,
 'sub_rank': 0,
 'type': 'top_stories',
 'sub_type': None,
 'title': 'Biden citizenship program for migrant spouses in US launches',
 'url': 'https://www.newsnationnow.com/us-news/immigration/biden-citizenship-program-migrant-spouses-us-launches/',
 'text': None,
 'cite': 'NewsNation',
 'details': None,
 'error': None,
 'serp_rank': 0}
```


#### 4. Save HTML and Metadata

Recommended: Append html and meta data as lines to a json file for larger or 
ongoing collections.

```python
se.save_serp(append_to='serps.json')
```

Alternative: Save individual html files in a directory, named by a provided or (default) generated `serp_id`. Useful for smaller qualitative explorations where you want to quickly look at what is showing up. No meta data is saved, but timestamps could be recovered from the files themselves.

```python
se.save_serp(save_dir='./serps')
```

#### 5. Save Parsed Results

Save to a json lines file.

```python
se.save_results(append_to='results.json')
```

---  
## Localization

To conduct localized searches--from a location of your choice--you only need  
one additional data point: The __"Canonical Name"__ of each location. These are  
available online, and can be downloaded using a built in function  
(`ws.download_locations()`) to check for the most recent version.  

A brief guide on how to select a canonical name and use it to conduct a  
localized search is available in a [jupyter notebook here](https://gist.github.com/gitronald/45bad10ca2b78cf4ec1197b542764e05).  


---
## Contributing

Happy to have help! If you see a component that we aren't covering yet, please add it using the process below. If you aren't sure about how to write a parser, you can also create an issue and I'll try to check it out. When creating that type of issue, providing the query that produced the new component and the time it was seen are essential, a screenshot of the component would be helpful, and the HTML would be ideal. Feel free to reach out if you have questions or need help.


### Repair or Enhance a Parser

1. Examine parser names in `/component_parsers/__init__.py`
2. Find parser file as `/component_parsers/{cmpt_name}.py`.

### Add a Parser

1. Add classifier to `classifiers/{main,footer,headers}.py`  
2. Add parser as new file in `/component_parsers`  
3. Add new parser to imports and catalogue in `/component_parsers/__init__.py`  

### Testing

Run tests:
```bash
uv run pytest tests/ -q
```

Update snapshots:
```bash
uv run pytest tests/ --snapshot-update
```

Show snapshot diffs with `-vv`:
```bash
uv run pytest tests/ -vv
```

Run a specific snapshot test by serp_id prefix:
```bash
uv run pytest tests/ -k "45b6e019bfa2"
```

### Test Fixtures

Tests load from compressed fixtures in `tests/fixtures/`. To update fixtures after collecting new demo data:

```bash
uv run python scripts/condense_fixtures.py 0.6.7
uv run pytest tests/ --snapshot-update
```

---
## GitHub Actions

**Test Workflow** (`.github/workflows/test.yml`)
Runs the test suite on every push to `dev`.

**Release Workflow** (`.github/workflows/publish.yml`)
Publishes to PyPI when a pull request is merged into `master`:
- Builds the package using uv
- Publishes using trusted publishing (no API tokens required)

To release a new version:
1. Merge `dev` into `master` via PR
2. Once merged, the package is automatically published to PyPI

---
## Similar Packages

Many of the packages I've found for collecting web search data via python are no longer maintained, but others are still ongoing and interesting or useful. The primary strength of WebSearcher is its parser, which provides a level of detail that enables examinations of SERP [composition](http://dl.acm.org/citation.cfm?doid=3178876.3186143) by recording the type and position of each result, and its modular design, which has allowed us to (itermittenly) maintain it for so long and to cover such a wide array of component types (currently 25 without considering `sub_types`). Feel free to add to the list of packages or services through a pull request if you are aware of others:

- https://github.com/jarun/googler
- http://googolplex.sourceforge.net
- https://github.com/Jayin/google.py
- https://github.com/ecoron/SerpScrap
- https://github.com/henux/cli-google
- https://github.com/Kaiz0r/netcrawler
- https://github.com/nabehide/WebSearch
- https://github.com/NikolaiT/se-scraper
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
- https://github.com/bisoncorps/search-engine-parser
- https://github.com/the-markup/investigation-google-search-audit
- http://googlesystem.blogspot.com/2008/04/google-search-rest-api.html
- https://valentin.app
- https://app.samuelschmitt.com/

---  
## License

Copyright (C) 2017-2026 Ronald E. Robertson <rer@acm.org>

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
