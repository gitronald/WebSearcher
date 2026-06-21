# WebSearcher
## Tools for conducting and parsing web searches  
[![PyPI version](https://badge.fury.io/py/WebSearcher.svg)](https://badge.fury.io/py/WebSearcher)

This package provides tools for conducting algorithm audits of web search and 
includes a scraper built on `selenium` with tools for geolocating, conducting, 
and saving searches. It also includes a modular parser built on `selectolax` 
for decomposing a SERP into list of components with categorical classifications 
and position-based specifications. 

## Recent Changes

- `0.10.1`: Reorganized the flat parse modules into a single `WebSearcher.parsers` package (public entrypoints unchanged; deep imports of the old flat paths must switch) and hardened the parse pipeline -- every component is classified before any is parsed, and `Component.to_dict()` now returns a copy -- with output byte-identical (snapshot-pinned). Also dropped the `snakeviz`/`ipykernel` dev dependencies to evict the transitive `tornado` advisories
- `0.10.0`: Reliable CAPTCHA detection from the `/sorry/` block-redirect URL (not just the page text), with the browser backends capturing the live URL and HTML on a blocked request. Automated the geotargets locations refresh (`update_locations_file`, a tracked CSV + ledger, and a weekly cron). Richer parsed output under the two-tier result schema — right-hand knowledge-panel entity facts, `evlb_*` video `details`, item `visible`/`timestamp` flags, and the per-result `error` moved into `details` (**breaking output**); `local_results` `sub_type` is now a closed set (**breaking output**). Added `SearchEngine.to_record()`/`save_record()`, optimized the parse hot path, and renamed the internal `search_methods` subpackage to `searchers` (the public `SearchEngine` imports are unchanged)
- `0.9.0`: **Breaking** internal rewrite of the parse pipeline onto `selectolax` (lexbor backend) for ~2x faster parsing, dropping the BeautifulSoup + lxml runtime dependencies. The `parse_serp`/`SearchEngine` API and output schema are unchanged, but `make_soup`/`load_soup` now return a `selectolax` node and the right-hand knowledge-panel rows are retyped to `type=side_bar`. Also broadens `kp-wholepage` knowledge-panel coverage, adds `election_*` component types and a `features.main_layout` field, and ships the demos in-package via a single `ws-demo` command

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
  - [Running on a headless server (Xvfb)](#running-on-a-headless-server-xvfb)
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

WebSearcher ships runnable demos inside the package, so they work straight after `pip install WebSearcher`. Search and parse a query with `ws-demo search`, passing the query as the first argument:

```bash
uv run ws-demo search "election news"
```

This collects the SERP, parses it, and saves the outputs (described below). The other demos run the same way: `ws-demo parse <file>` (offline parse of one HTML file), `ws-demo searches` (a battery of queries spanning component types), `ws-demo headers <query>` (custom request headers), and `ws-demo locations <query>` (localized search). Search results change constantly, especially for news, but you can review the parsed components of any saved query with `ws-demo show` (add `--details` for a details column, `--list` to enumerate saved queries):

```bash
uv run ws-demo show "election news"
```

```
WebSearcher v0.9.0a0 | qry='election news' | 22 components

type              title                                                         url
----------------  ------------------------------------------------------------  ------------------------------------------------------------
ad                Latest Election News                                          https://www.election-integrity.org/news
top_stories       Latest on California governor election as public awaits r...  https://www.usatoday.com/story/news/politics/elections/20...
top_stories       California election results still undecided as Los Angele...  https://www.foxnews.com/politics/california-election-resu...
top_stories       California Governor Primary Election 2026 Live Results        https://www.nbcnews.com/politics/2026-primary-elections/c...
local_news        San Mateo County elections division has more than 100K ba...  https://localnewsmatters.org/2026/06/05/san-mateo-county-...
local_news        Sorry, Silicon Valley, it isn’t that easy to buy an election  https://sfstandard.com/2026/06/03/matt-mahan-silicon-vall...
general           California pushes back on Trump's primary election ...        https://www.nbcsandiego.com/news/local/california-trump-c...
general           5 things to know about California's election results          https://calmatters.org/politics/2026/06/primary-election-...
videos            Latest on California governor, L.A. mayor primary electio...  https://www.youtube.com/watch?v=--eGQRVD6ms
videos            KTLA 5 News Election Coverage: Votes continue to be ... Y...  https://www.youtube.com/watch?v=wMXxRGZHjKg
general           Elections 2026                                                https://www.npr.org/sections/elections/
general           Ballotpedia.org                                               https://ballotpedia.org/Main_Page
general           Election Night Results                                        https://electionresults.sos.ca.gov/
```

By default, that script will save the outputs to a directory (`data/demo-ws-{version}/`) as JSON lines files: `serps.json` (the HTML plus search metadata), `parsed.json` (the parsed results and features), and `searches.json` (the search metadata only, excluding HTML).

```sh
ls -hal data/demo-ws-v0.9.0a0/
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
se.search('election news')                 # 2. Conduct a search
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
se.search('election news')
# 2026-05-26 09:14:22.318 | INFO | WebSearcher.searchers | 200 | election news
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
 'type': 'ad',
 'sub_type': 'standard',
 'title': 'Latest Election News',
 'url': 'https://www.election-integrity.org/news',
 'text': 'Latest Election News',
 'cite': 'https://www.election-integrity.org',
 'details': None,
 'serp_rank': 0}
```

##### Result schema

Every result shares the same lean **core** fields (`type`, `sub_type`, `title`,
`url`, `text`, `cite`, plus the `section` / `cmpt_rank` / `sub_rank` / `serp_rank`
rank metadata). Anything extra lives in **`details`**, which is either `None`
(a clean row) or a dict that always carries a `type`:

```python
# clean row -- nothing extra
{..., 'details': None}

# typed content payload (a specific label)
{..., 'details': {'type': 'ratings', 'rating': '4.6', 'n_reviews': '6.3K'}}
{..., 'details': {'type': 'hyperlinks', 'items': [{'url': '...', 'text': '...'}]}}

# metadata-only row (generic 'item' type): a parse error, a hidden
# carousel-tail card, an extracted timestamp/thumbnail, etc.
{..., 'details': {'type': 'item', 'error': 'no subcomponents parsed'}}
{..., 'details': {'type': 'item', 'visible': False, 'heading': 'What people are saying'}}
{..., 'details': {'type': 'item', 'timestamp': '2 hours ago', 'img_url': 'https://...'}}
```

The reserved metadata keys (`error`, `visible`, `timestamp`, `img_url`) are
recorded only when they carry information — `visible` only when `False`, the
others when present — so the common case keeps `details` as `None`.


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
## Running on a headless server (Xvfb)

The browser backends (`selenium` -- the default -- plus the optional `patchright` and
`zendriver`) drive a **real, visible** Chrome: search engines reliably block Chrome's own
`--headless` mode, so the browser must run *headed*. On a server, CI runner, or container with
no display (`$DISPLAY` unset), a headed Chrome has nothing to attach to and won't launch. (The
`requests` backend is pure HTTP and needs no display -- this only applies to the browser
backends.)

The fix is [**Xvfb**](https://www.x.org/releases/X11R7.7/doc/man/Xvfb.1.xhtml), an in-memory X
display server: it lets Chrome run genuinely headed -- no headless code path, no monitor, no
GPU. Install it (Debian/Ubuntu):

```bash
sudo apt-get install -y xvfb
```

Then wrap your collection command with `xvfb-run`:

```bash
env -u DISPLAY xvfb-run -a --server-args="-screen 0 1920x1080x24" \
  python your_collection_script.py
```

- `env -u DISPLAY` removes any inherited display so the run can't silently fall back to a real
  one (e.g. an X-forwarded SSH session) -- the display Xvfb creates is then the only one in scope.
- `xvfb-run -a` auto-picks a free display number, so concurrent jobs don't collide.
- `-screen 0 1920x1080x24` gives a realistic window geometry.

The collection code itself is unchanged:

```python
import WebSearcher as ws

se = ws.SearchEngine()            # default browser backend, headed
se.search("immigration news")
se.parse_serp()
se.save_serp(append_to="serps.json")
```

If you parallelize collection across processes, one shared Xvfb covers them all -- child
workers inherit the parent's `DISPLAY`, so wrap the top-level command once rather than starting
an Xvfb per worker.


---
## Contributing

Happy to have help! If you see a component that we aren't covering yet, please add it using the process below. If you aren't sure about how to write a parser, you can also create an issue and I'll try to check it out. When creating that type of issue, providing the query that produced the new component and the time it was seen are essential, a screenshot of the component would be helpful, and the HTML would be ideal. Feel free to reach out if you have questions or need help.


### Repair or Enhance a Parser

1. Examine parser names in `/parsers/components/__init__.py`
2. Find parser file as `/parsers/components/{cmpt_name}.py`.

### Add a Parser

1. Add classifier to `classifiers/{main,footer,headers}.py`  
2. Add parser as new file in `/parsers/components`  
3. Add new parser to imports and catalogue in `/parsers/components/__init__.py`  

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
uv run pytest tests/ -k "4f4d0fed0592"
```

### Test Fixtures

Tests load from the consolidated compressed corpus `tests/fixtures/serps.json.bz2`. After adding or updating records, refresh the snapshots:

```bash
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
