# WebSearcher
## Tools for conducting and parsing web searches  
[![PyPI version](https://badge.fury.io/py/WebSearcher.svg)](https://badge.fury.io/py/WebSearcher)

This package provides tools for conducting algorithm audits of web search and 
includes a scraper built on `requests` with tools for geolocating, conducting, 
and saving searches. It also includes a modular parser built on `BeautifulSoup` 
for decomposing a SERP into list of components with categorical classifications 
and position-based specifications.

## Table of Contents

- [WebSearcher](#websearcher)
  - [Tools for conducting and parsing web searches](#tools-for-conducting-and-parsing-web-searches)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
  - [Usage](#usage)
      - [Prepare a search](#prepare-a-search)
      - [Conduct a search](#conduct-a-search)
    - [Save a Search](#save-a-search)
  - [Localization](#localization)
  - [Contributing](#contributing)
    - [Repair or Enhance a Parser](#repair-or-enhance-a-parser)
    - [Add a Parser](#add-a-parser)
    - [Testing](#testing)
  - [Recent Changes](#recent-changes)
  - [Similar Packages](#similar-packages)
  - [License](#license)

---  
## Getting Started

```bash
# Install pip version
pip install WebSearcher

# Install Github development version - less stable, more fun!
pip install git+https://github.com/gitronald/WebSearcher@dev
```

---  
## Usage

#### Prepare a search
```python
import WebSearcher as ws

# Initialize crawler with optional defaults (headers, logs, ssh tunnels)
se = ws.SearchEngine()
vars(se)
```
```python
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

<!-- Conduct web searches from a location of choice. -->

To conduct localized searches--from a location of your choice--you only need one additional data point: The __"Canonical Name"__ of each location.   
These are available online, and can be downloaded using a built in function (`ws.download_locations()`) that checks for the most recent version.  

A brief guide on how to select a canonical name and use it to conduct a localized search is available in a [jupyter notebook here](https://gist.github.com/gitronald/45bad10ca2b78cf4ec1197b542764e05).  



---
## Contributing

Happy to have help! If you see a component that we aren't covering yet, please add it using the process below. If you have other improvements, feel free to add them any way you can.  


### Repair or Enhance a Parser

1. Examine parser names in `/component_parsers/__init__.py`
2. Find parser file as `/component_parsers/{cmpt_name}.py`.

### Add a Parser

1. Add classifier to `component_classifier.py`, as `'cmpt_name'`
2. Add parser file in `/component_parsers` as `cmpt_name.py`, with function `parse_cmpt_name`.
3. Add import for `parse_cmpt_name` in `/component_parsers/__init__.py`

### Testing
Run tests:
```
pytest
```

Update snapshots:
```
pytest --snapshot-update
```

Running pytest with the `-vv` flag will show a diff of the snapshots that have changed:
```
pytest -vv
```

With the `-k` flag you can run a test for a specific html file:
```
pytest -k "1684837514.html"
```

---
## Recent Changes

`0.3.10` - Updated component classifier for images, added exportable header text mappings, added gist on localized searches.

`0.3.9` - Small fixes for video url parsing

`0.3.8` - Using SERP pydantic model, added github pip publishing workflow

`0.3.7` - Fixed localization, parser and classifier updates and fixes, image subtypes, changed rhs component handling.

`0.3.0` - `0.3.6` - Parser updates for SERPs from 2022 and 2023, standalone extractors file, added pydantic, reduced redundancies in outputs.

`2020.0.0`, `2022.12.18`, `2023.01.04` - Various updates, attempt at date versioning that seemed like a good idea at the time ¯\\\_(ツ)\_/¯

<!-- refs/tags/v2022.12.18 -->
<!-- refs/tags/v2023.01.04 -->

`0.2.15` - Fix people-also-ask and hotel false positives, add flag for left-hand side bar

`0.2.14` - Add shopping ads carousel and three knowledge subtypes (flights, hotels, events)

`0.2.13` - Small fixes for knowledge subtypes, general subtypes, and ads

`0.2.12` - Try to brotli decompress by default

`0.2.11` - Fixed local result parser and no return in general extra details

`0.2.10` - a) Add right-hand-side knowledge panel and top image carousel, b) Add knowledge and general component subtypes, c) Updates to component classifier, footer, ad, and people_also_ask components

`0.2.9` - Various fixes for SERPs with a left-hand side bar, which are becoming more common and change other parts of the SERP layout.

`0.2.8` - Small fixes due to HTML changes, such as missing titles and URLs in general components

`0.2.7` - Added fix for parsing twitter cards, removed pandas dependencies and 
several unused functions, moving towards greater package simplicity.

`0.2.6` - Updated ad parser for latest format, still handles older ad format.

`0.2.5` -  Google Search, like most online platforms, undergoes changes over time. 
These changes often affect not just their outward appearance, but the underlying 
code that parsers depend on. This makes parsing a goal with a moving target. 
Sometime around February 2020, Google changed a few elements of their HTML 
structure which broke this parser. I created this patch for these changes, 
but have not tested its backwards compatibility (e.g. on SERPs collected prior to 
2/2020). More generally, there's no guarantee on future compatibility. In fact, 
there is almost certainly the opposite: more changes will inevitably occur. 
If you have older data that you need to parse and the current parser doesn't work, 
you can try using `0.2.1`, or send a pull request if you find a way to make both work!


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

Copyright (C) 2017-2024 Ronald E. Robertson <rer@acm.org>

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
