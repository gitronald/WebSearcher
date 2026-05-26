# WebSearcher
## Tools for conducting and parsing web searches  
[![PyPI version](https://badge.fury.io/py/WebSearcher.svg)](https://badge.fury.io/py/WebSearcher)

This package provides tools for conducting algorithm audits of web search and 
includes a scraper built on `selenium` with tools for geolocating, conducting, 
and saving searches. It also includes a modular parser built on `BeautifulSoup` 
for decomposing a SERP into list of components with categorical classifications 
and position-based specifications. 

## Recent Changes

- `0.8.4`: Reclassified shopping/commercial blocks that previously emitted hollow `general` rows (29 -> 0) into new component types — `products` (grid/brands), `promo` (shopping deals banner), `most_read_articles`, and `buying_guide` — plus a `general` `image_strip` sub_type
- `0.8.3`: Recovered parser coverage for historical/edge layouts — legacy 2024-SGE `ai_overview` content + `unavailable` state, a new `recipes` parser, empty `knowledge` (featured_results/dictionary/panel_rhs) extraction, `twitter_cards` card titles, and modern `shopping_ads` PLA cards
- `0.8.2`: Parse pipeline optimization — ~24% faster per-SERP `parse_serp` (dropped whole-document `str(soup)`, classifier signal preconditions, lazy `SearchEngine` import); fixed the dormant `is_valid` hidden-survey filter
- `0.8.1`: Breaking — `ai_overview` promoted to a top-level component type with a section-aware parser, restructured `details.sources`, and section/lede `citations`; security and dependency bumps
- `0.8.0`: Added `jobs`, `flights`, `videos`, and `knowledge_subcard` parsers/classifiers; expanded `local_results` details; modernized `available_on`, `perspectives`, `searches_related`, and rating-widget selectors; added inspection scripts
- `0.7.1`: Added component type registry and pyrefly type checking; refreshed CI/tooling (lint, format, type-check, tag-based publish); bumped Python floor to 3.12
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

There's an example search script that can be run from the command line with uv, passing the search query as the first argument.

```bash
uv run demo-search "election news"
```

This collects the SERP, parses it, and saves the outputs (described below). Search results change constantly, especially for news, but you can review the parsed components of any saved query with `show_parsed.py`:

```bash
uv run python scripts/show_parsed.py "election news" --cat-width 12
```

```
qry='election news', components=23

┌──────┬─────┬────────┬──────────────┬──────────────┬──────────────────────────────┬──────────────────────────────┬────────────┐
│ rank ┆ sub ┆ sec    ┆ type         ┆ sub_type     ┆ title                        ┆ url                          ┆ details    │
╞══════╪═════╪════════╪══════════════╪══════════════╪══════════════════════════════╪══════════════════════════════╪════════════╡
│ 0    ┆ 0   ┆ main   ┆ ad           ┆ standard     ┆ Latest Election News         ┆ https://www.election-integr… ┆ -          │
│ 1    ┆ 0   ┆ main   ┆ top_stories  ┆ -            ┆ 2026 Texas primary runoff e… ┆ https://www.cbsnews.com/tex… ┆ -          │
│ 1    ┆ 1   ┆ main   ┆ top_stories  ┆ -            ┆ Texas runoff election live … ┆ https://www.usatoday.com/st… ┆ -          │
│ 1    ┆ 2   ┆ main   ┆ top_stories  ┆ -            ┆ Texas’ raucous primary runo… ┆ https://www.texastribune.or… ┆ -          │
│ 1    ┆ 3   ┆ main   ┆ top_stories  ┆ -            ┆ Where to vote in El Paso, w… ┆ https://www.elpasotimes.com… ┆ -          │
│ 1    ┆ 4   ┆ main   ┆ top_stories  ┆ -            ┆ Texas voters head to polls … ┆ https://www.audacy.com/krld… ┆ -          │
│ 1    ┆ 5   ┆ main   ┆ top_stories  ┆ -            ┆ Texas elections live update… ┆ https://www.nbcnews.com/pol… ┆ -          │
│ 1    ┆ 6   ┆ main   ┆ top_stories  ┆ -            ┆ Trump claims 2020 election … ┆ https://www.reuters.com/wor… ┆ -          │
│ 2    ┆ 0   ┆ main   ┆ local_news   ┆ -            ┆ Get up to speed fast on the… ┆ https://www.mv-voice.com/ca… ┆ -          │
│ 2    ┆ 1   ┆ main   ┆ local_news   ┆ -            ┆ Column: My pick for Califor… ┆ https://www.latimes.com/cal… ┆ -          │
│ 2    ┆ 2   ┆ main   ┆ local_news   ┆ -            ┆ Voter turnout remains low i… ┆ https://www.cbs8.com/video/… ┆ -          │
│ 2    ┆ 3   ┆ main   ┆ local_news   ┆ -            ┆ California gubernatorial el… ┆ https://abc7news.com/post/c… ┆ -          │
│ 3    ┆ 0   ┆ main   ┆ general      ┆ -            ┆ Last-minute voter guide for… ┆ https://calmatters.org/poli… ┆ -          │
│ 4    ┆ 0   ┆ main   ┆ general      ┆ -            ┆ Matt Mahan facing campaign … ┆ https://abc7news.com/post/c… ┆ -          │
│ 5    ┆ 0   ┆ main   ┆ general      ┆ -            ┆ Election 2026: Results, new… ┆ https://www.cnn.com/electio… ┆ -          │
│ 6    ┆ 0   ┆ main   ┆ general      ┆ -            ┆ Ballotpedia.org              ┆ https://ballotpedia.org/Mai… ┆ -          │
│ 7    ┆ 0   ┆ main   ┆ videos       ┆ vertical     ┆ Voter turnout remains low i… ┆ https://www.youtube.com/wat… ┆ -          │
│ 7    ┆ 1   ┆ main   ┆ videos       ┆ vertical     ┆ Thomas Massie files stateme… ┆ https://www.youtube.com/wat… ┆ -          │
│ 7    ┆ 2   ┆ main   ┆ videos       ┆ vertical     ┆ Breaking down the Democrats… ┆ https://www.youtube.com/wat… ┆ -          │
│ 8    ┆ 0   ┆ main   ┆ general      ┆ -            ┆ Elections 2026               ┆ https://www.npr.org/section… ┆ -          │
│ 9    ┆ 0   ┆ main   ┆ general      ┆ -            ┆ Department of Elections      ┆ https://www.sf.gov/departme… ┆ -          │
│ 10   ┆ 0   ┆ main   ┆ general      ┆ -            ┆ Everything You Need to Vote… ┆ https://www.vote.org/        ┆ -          │
│ 11   ┆ 0   ┆ footer ┆ searches_re… ┆ people_also… ┆ -                            ┆ -                            ┆ text (n=8) │
└──────┴─────┴────────┴──────────────┴──────────────┴──────────────────────────────┴──────────────────────────────┴────────────┘
```

By default, that script will save the outputs to a directory (`data/demo-ws-{version}/`) as JSON lines files: `serps.json` (the HTML plus search metadata), `parsed.json` (the parsed results and features), and `searches.json` (the search metadata only, excluding HTML).

```sh
ls -hal data/demo-ws-v0.8.4/
```
```
total 1020K
drwxr-xr-x 2 user user 4.0K 2024-11-11 10:55 ./
drwxr-xr-x 8 user user 4.0K 2024-11-11 10:54 ../
-rw-r--r-- 1 user user  16K 2024-11-11 10:55 parsed.json
-rw-r--r-- 1 user user 2.0K 2024-11-11 10:55 searches.json
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
se.save_parsed(append_to='parsed.json')    # 5. Save parsed results

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
        "version_main": None,  # auto-detected from installed Chrome when None
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
se.save_parsed(append_to='parsed.json')
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

Many of the packages I've found for collecting web search data via python are no longer maintained, but others are still ongoing and interesting or useful. The primary strength of WebSearcher is its parser, which provides a level of detail that enables examinations of SERP [composition](http://dl.acm.org/citation.cfm?doid=3178876.3186143) by recording the type and position of each result, and its modular design, which has allowed us to (itermittenly) maintain it for so long and to cover such a wide array of component types (currently 45 without considering `sub_types`). Feel free to add to the list of packages or services through a pull request if you are aware of others:

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
