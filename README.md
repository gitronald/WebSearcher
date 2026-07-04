# WebSearcher
## Tools for conducting and parsing web searches  
[![PyPI version](https://badge.fury.io/py/WebSearcher.svg)](https://badge.fury.io/py/WebSearcher)

This package provides tools for conducting algorithm audits of web search and 
includes tools for geolocating, conducting, and saving searches that are built 
around `patchright`. It also includes a modular parser built on `selectolax` 
for quickly decomposing a SERP into list of components with categorical 
classifications and position-based specifications. 

## Recent Changes

- `0.11.0`: **Breaking** -- dropped the `selenium`, `zendriver`, and `playwright` backends; `patchright` is now the default and drives an installed Google Chrome (`patchright install chrome` if missing). Crawl logs are now JSON Lines only, and `SearchEngine` gained `close()` and context-manager teardown
- `0.10.0`: Reliable `/sorry/` CAPTCHA detection, an automated weekly geotargets refresh, and richer two-tier parsed output (**breaking output**)
- `0.9.0`: **Breaking** -- rewrote the parser onto `selectolax` for ~2x faster parsing (dropping BeautifulSoup + lxml) and shipped in-package demos via `ws-demo`

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
        - [Result schema](#result-schema)
      - [4. Save HTML and Metadata](#4-save-html-and-metadata)
      - [5. Save Parsed Results](#5-save-parsed-results)
      - [6. Close the Browser](#6-close-the-browser)
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

The default `patchright` browser backend drives Google Chrome
(`channel="chrome"`), which pip can't install automatically. If Chrome
isn't already installed, run this once after installing:

```bash
patchright install chrome
```

Or use patchright's bundled Chromium instead: run `patchright install chromium`
and pass `patchright_config={"channel": "chromium"}`.

---  
## Usage

### Example Search Script

WebSearcher ships runnable demos inside the package, so they work straight after `pip install WebSearcher`. Search and parse a query with `ws-demo search`, passing the query as the first argument:

<!-- demo:search:start -->
```bash
uv run ws-demo search "election news"
```
<!-- demo:search:end -->

This collects the SERP, parses it, and saves the outputs (described below). The other demos run the same way: `ws-demo parse <file>` (offline parse of one HTML file), `ws-demo searches` (a battery of queries spanning component types), `ws-demo headers <query>` (custom request headers), and `ws-demo locations <query>` (localized search). Search results change constantly, especially for news, but you can review the parsed components of any saved query with `ws-demo show` (add `--details` for a details column, `--list` to enumerate saved queries):

<!-- demo:show:start -->
```bash
uv run ws-demo show "election news"
```

```
WebSearcher v0.11.0 | qry='election news' | 15 components

type              title                                                         url
----------------  ------------------------------------------------------------  ------------------------------------------------------------
top_stories       Jack Smith says he's 'very concerned what's going to happ...  https://www.cnbc.com/2026/07/02/jack-smith-trump-intervie...
top_stories       Trump Is Getting Tired of Losing Election Cases               https://www.theatlantic.com/politics/2026/07/trump-electi...
top_stories       Trump Promises Republicans They ‘Will Not Lose An Electio...  https://www.huffpost.com/entry/trump-republicans-election...
top_stories       Trump Targets Not Just Georgia’s Vote, but Also Trust in ...  https://www.nytimes.com/2026/07/03/us/politics/trump-geor...
top_stories       Keiko Fujimori declared winner of razor-edge Peru election    https://www.cnn.com/2026/07/03/americas/fujimori-wins-per...
general           Governor Gavin Newsom marks Fourth of July with a call fo...  https://www.gov.ca.gov/2026/07/04/governor-gavin-newsom-m...
general           Elections                                                     https://www.npr.org/sections/elections/
general           Ballotpedia.org                                               https://ballotpedia.org/Main_Page
general           Newsom to unveil felony penalties for election interferen...  https://www.abc10.com/article/news/politics/newsom-to-unv...
general           EAC News & Events | U.S. Election Assistance Commission       https://www.eac.gov/news-and-events
general           'It's going to be a battle': How Dems plan to combat Trum...  https://www.youtube.com/watch?v=1-H7R4f_ZoE
general           Election Night Results | 2026 Primary Election | Californ...  https://electionresults.sos.ca.gov/
general           Election News, Polls and Results - 270toWin                   https://www.270towin.com/news/
general           2026 Election Results: California and Bay Area Primary ...    https://www.kqed.org/voterguide
searches_related
```
<!-- demo:show:end -->

By default, that script will save the outputs to a directory (`data/demo-ws-v{version}/`) as JSON lines files: `serps.json` (the HTML plus search metadata), `parsed.json` (the parsed results and features), and `searches.json` (the search metadata only, excluding HTML).

### Step by Step 

Example search and parse pipeline:

```python
import WebSearcher as ws
se = ws.SearchEngine()                     # 1. Initialize collector
se.search('election news')                 # 2. Conduct a search
se.parse_serp()                            # 3. Parse search results
se.save_serp(append_to='serps.json')       # 4. Save HTML and metadata
se.save_parsed(append_to='parsed.json')    # 5. Save parsed results
se.close()                                 # 6. Close the browser
```

#### 1. Initialize Collector

```python
import WebSearcher as ws

# Initialize collector with method and other settings.
# `patchright` is the default browser backend; it drives your installed
# Google Chrome (channel="chrome").
se = ws.SearchEngine(
    method="patchright", 
    patchright_config = {
        "headless": False,
        "channel": "chrome",
        "user_data_dir": "",  # a temp profile is created when empty
    }
)
```   

#### 2. Conduct a Search

Logs are emitted as JSON Lines -- one structured object per line, with only the
keys that apply to the event:

```python
se.search('election news')
# {"timestamp": "2026-07-04T13:37:12.399-07:00", "pid": 62981, "level": "INFO", "event": "search", "response_code": 200, "qry": "election news", "loc": ""}
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
 'title': "Jack Smith says he's 'very concerned what's going to happen next election' under Trump",
 'url': 'https://www.cnbc.com/2026/07/02/jack-smith-trump-interview-doj.html',
 'text': None,
 'cite': None,
 'details': None,
 'serp_rank': 0}
```

##### Result schema

Every result shares the same lean **core** fields (`type`, `sub_type`, `title`,
`url`, `text`, `cite`, plus the `section` / `cmpt_rank` / `sub_rank` / 
`serp_rank` rank metadata). Anything extra lives in **`details`**, which is 
either `None` (a clean row) or a dict that always carries a `type`:

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

#### 6. Close the Browser

The browser window stays open until the engine is closed -- close it explicitly
when done, or use the engine as a context manager to close it automatically:

```python
se.close()

# or scope the whole pipeline:
with ws.SearchEngine() as se:
    se.search('election news')
    ...
```

---  
## Localization

To conduct localized searches--from a location of your choice--you only need  
one additional data point: The __"Canonical Name"__ of each location.  

The latest dataset is shipped in this repository at  
[`data/locations/geotargets.csv`](data/locations/geotargets.csv). 
An accompanying [`data/locations/ledger.csv`](data/locations/ledger.csv) 
records the upstream release each refresh pulled. The committed copies of these
two files are kept current automatically by a weekly workflow. Details on this 
are available in the [GitHub Actions](#github-actions) section ("Update 
locations") below. You can also fetch the most recent version yourself by using
the built-in `ws.download_locations()`.  

A brief guide on how to select a canonical name and use it to conduct a  
localized search is available in a [jupyter notebook here](https://gist.github.com/gitronald/45bad10ca2b78cf4ec1197b542764e05).  


---
## Running on a headless server (Xvfb)

The `patchright` backend (the default) drives a **real, visible** Chrome: 
Chrome's own `--headless` mode can be reliably blocked, so the browser must run
*headed*. On a server, CI runner, or container with no display (`$DISPLAY` 
unset), a headed Chrome has nothing to attach to and won't launch.

The fix is [**Xvfb**](https://www.x.org/releases/X11R7.7/doc/man/Xvfb.1.xhtml), 
an in-memory X display server: it lets Chrome run genuinely headed -- no 
headless code path, no monitor, no GPU. This applies to Linux only (macOS Chrome
uses the native window server, not X11). Install it (Debian/Ubuntu):

```bash
sudo apt-get install -y xvfb
```

Then wrap your collection command with `xvfb-run`:

```bash
env -u DISPLAY xvfb-run -a --server-args="-screen 0 1920x1080x24" \
  python your_collection_script.py
```

- `env -u DISPLAY` removes any inherited display so the run can't silently fall back to a real one (e.g. an X-forwarded SSH session) -- the display Xvfb creates is then the only one in scope.
- `xvfb-run -a` auto-picks a free display number, so concurrent jobs don't collide.
- `-screen 0 1920x1080x24` gives a realistic window geometry. The `1920x1080x24` is `width x height x depth` -- a 1920x1080 framebuffer at 24-bit (true-color) depth, i.e. a standard 1080p desktop.

The collection code itself is unchanged:

```python
import WebSearcher as ws

se = ws.SearchEngine()
se.search("immigration news")
se.parse_serp()
se.save_serp(append_to="serps.json")
```

If you parallelize collection across processes, one shared Xvfb covers them 
all. Child workers inherit the parent's `DISPLAY`, so wrap the top-level 
command once rather than starting an Xvfb per worker.


---
## Contributing

Happy to have help! If you see a component that we aren't covering yet, please add it using the process below. If you aren't sure about how to write a parser, you can also create an issue and I'll try to check it out. When creating that type of issue, providing the query that produced the new component and the time it was seen are essential, a screenshot of the component would be helpful, and the HTML would be ideal. Feel free to reach out if you have questions or need help.


### Repair or Enhance a Parser

1. Examine parser names in `/parsers/components/__init__.py`
2. Find parser file as `/parsers/components/{cmpt_name}.py`.

### Add a Parser

1. Register the component type in `parsers/component_types.py` -- the single source of truth for `name`, `label`, `sections`, and (for header-text classification) `header_texts`. Dispatch and classification are derived from this registry.  
2. Add classifier to `classifiers/{main,footer,headers}.py` for structural signals (header-text matches instead go in the registry's `header_texts`)  
3. Add parser as new file in `/parsers/components`  
4. Add new parser to imports and the `PARSERS` catalogue in `/parsers/components/__init__.py` (its section dispatch and label are derived by joining this against the registry, so the `name` must match step 1)  

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

**Tests** (`.github/workflows/test.yml`)  
Runs on every push and pull request to `dev`, `master`, and `feature/**` branches, across a Python 3.12 / 3.13 / 3.14 matrix: `ruff check`, `ruff format --check`, `pyrefly check`, then `pytest` with coverage.

**Publish** (`.github/workflows/publish.yml`)  
Triggered by pushing a `v*` tag. Builds the package with `uv build` and publishes to PyPI via trusted publishing (no API tokens). It only runs when the repository variable `PUBLISH_ENABLED` is `"true"`; otherwise both jobs skip. For instructions on how to set this, see: [Enable or disable PyPI publishing](.planners/guides/enable-pypi-publishing.md).

**Update locations** (`.github/workflows/update-locations.yml`)  
Weekly cron (Mondays 06:00 UTC) plus manual dispatch. Refreshes the geotargets CSV (`python -m WebSearcher.locations`) and opens a PR only when the data changed.

**Renovate** (`.github/workflows/renovate.yml`)  
Weekly cron plus manual dispatch. Self-hosted [Renovate](https://docs.renovatebot.com/) opens dependency-update PRs (config in `.github/renovate.json`).

To release a new version:
1. Tag a `vX.Y.Z` release on `master`.
2. Pushing the tag runs the publish workflow, which builds and uploads to PyPI (when `PUBLISH_ENABLED` is `"true"`).

---
## Similar Packages

Many of the packages I've found for collecting web search data via python are no longer maintained, but others are still ongoing and interesting or useful. The primary strength of WebSearcher is its parser, which provides a level of detail that enables examinations of SERP [composition](http://dl.acm.org/citation.cfm?doid=3178876.3186143) by recording the type and position of each result, and its modular design, which has allowed us to (itermittenly) maintain it for so long and to cover such a wide array of component types (currently 46 registered in `parsers/component_types.py`, before counting `sub_types`). Feel free to add to the list of packages or services through a pull request if you are aware of others:

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
