---
id: 69
slug: search-pagination
status: draft
branch:
created: 2026-10-29T10:20:59-07:00
concluded:
pr:
---

# Replace num_results with start-offset pagination

## Plan

### Goal

Let a caller collect result pages past the first by passing Google's `start` offset, and
remove `num_results`, which Google no longer honors.

### Background

`SearchEngine.search(..., num_results=N)` sends Google's `num` URL parameter
(`SearchParams.url_params` in `WebSearcher/models/searches.py`). Google stopped honoring
it in September 2025 and has confirmed that it does not support a results-per-page
parameter:
<https://searchengineland.com/google-search-confirms-it-does-not-support-the-results-per-page-parameter-462244>.

A `requests` search with `num_results=100` now returns the same page as one without it.
The `general` counts match, the pagination footer still links to `start=10` through
`start=90` (the 10-per-page layout), and the next-page links drop `num`. The argument
has no effect except to add `&num=N` to the URL that gets recorded.

Google still paginates through `start`. The footer's next-page links are
`/search?q=...&start=10` and so on, alongside per-session tokens (`sca_esv`, `sxsrf`,
`ei`). Today the only way to get past the first page is to build the URL by hand,
because `url_params` builds only `q`, `num`, `hl`, and `uule`.

Current wiring:

- `WebSearcher/models/searches.py`: the `SearchParams.num_results` field and the
  `"num": self.num_results` entry in `url_params`
- `WebSearcher/searchers/searchers.py`: the `num_results` parameter of
  `SearchEngine.search()`, its docstring, and its pass-through into `SearchParams.create`
- `tests/test_models.py`: `test_search_params_url_with_num_results` and the
  `num_results: None` case beside it

### Decisions

1. **Remove `num_results` outright; don't deprecate it.** It already does nothing, so
   a deprecation cycle would only keep a silent no-op alive. Drop the field, the `num`
   URL entry, the `search()` parameter, its docstring line, and its tests. A caller
   that still passes `num_results=` gets a `TypeError`, and the CHANGELOG `Removed`
   entry says why and links the source above.
2. **Add a `start` offset, not a page number.** Add `start: int | None` to
   `SearchParams` and `SearchEngine.search()`. `url_params` emits `start` only when it
   is a positive int, so `None` and `0` both give today's first-page URL, byte for
   byte. Use Google's own parameter, as `num` did, rather than a 1-based `page` that
   assumes a fixed page size; a page size of 10 is what Google serves today, not a
   documented contract.
3. **Record the offset on the SERP.** Add `start` to `SearchParams.to_serp_output()` and
   a `start: int | None` field to `BaseSERP`, so a saved SERP says which page it is
   without anyone having to parse its URL. `serp_id` already hashes the timestamp, so
   page SERPs get distinct ids with no change.
4. **One request per page; no pagination loop in this plan.** `search()` fetches the
   one page it is given. A caller pages by calling it with `start=10`, `20`, and so on.
   Whether WebSearcher should ship a multi-page helper (paced, stopping on an empty or
   short page) depends on what the investigation finds about deep pages and blocking,
   and is a follow-up.
5. **Both backends take the offset through the URL.** Neither backend changes:
   `requests` and patchright both load `search_params.url`, and patchright already
   starts each request from a blank page, so page N does not depend on page N-1 having
   been loaded.
6. **Parsing stays per page.** A page past the first is parsed as its own SERP, and
   ranks restart at 0. It may lack first-page components (AI overview, knowledge
   panel, top stories); a parse that finds only `general` rows and `searches_related`
   is the expected shape, not a regression. No cross-page rank offset in this plan.
7. **Demo flag.** `ws-demo search` gets `--start N`, passed through to `search()`.
   If plan 068 lands first, it goes on `websearcher demo search` instead.
8. **CHANGELOG** `[Unreleased]`: `Removed` for `num_results` (with the source link),
   `Added` for `start` and the `BaseSERP.start` field.

### Investigation (first, by hand, against live Google)

Before writing the code, measure what a bare offset URL returns. Use a handful of
queries on each backend, paced like a normal crawl, and save every SERP for later
inspection. Record the findings in this plan's Log.

- Does `/search?q=<q>&start=10`, built without the footer's session tokens, return
  page 2? Compare it with the page the footer's own next-page link returns.
- Do the `general` results on page 2 overlap page 1's? How much overlap is normal
  (Google can repeat a host), and how much means the offset was ignored?
- How deep does a query go? Fetch `start=50` and `start=90`, and note where pages come
  back short or empty, or where Google appends `filter=0` ("repeat the search with the
  omitted results included").
- Do page SERPs parse cleanly: no new `unknown` families, the `#search` container
  present, and the same `has_search` behavior?
- Does paging get blocked sooner (a 429, a `/sorry/` CAPTCHA) than the same number of
  first-page searches?

A finding that a bare offset is ignored or reshuffled changes decision 5: the URL
would need the session tokens from page N-1's footer, so pages could no longer be
fetched independently. Revise the decisions before implementing.

### Tests

- `SearchParams` with `start=10` puts `start=10` in the URL; with `start=None` or
  `start=0` the URL has no `start=` and matches today's URL exactly.
- `num` is gone: `SearchParams.create({"qry": ..., "num_results": 20})` builds a URL
  with no `num=`. `BaseConfig` is a pydantic model with the default `extra="ignore"`, so
  the stale key is dropped silently, not rejected; `search(num_results=...)` is what
  raises the `TypeError`.
- `search()` passes `start` through to the recorded `serp["url"]` and `serp["start"]`
  (with the requests backend mocked).
- `ws-demo search --start 10` reaches `search()` with `start=10`.

### Order

1. Investigation (Log the findings; revise decisions 4-6 if they say to)
2. Remove `num_results` (decision 1) and its tests
3. Add `start` to `SearchParams`, `search()`, and `BaseSERP` (decisions 2-3)
4. Demo flag (decision 7)
5. CHANGELOG (decision 8)

### Out of scope

- A multi-page collection helper or crawl loop (decision 4's follow-up)
- Combining several pages into one ranked result list
- Continuous scroll or "More results" button loading

## Log

- **2026-10-29T10:42:11-07:00** — Tested bare `&start=N` URLs against live Google: WebSearcher 0.13.1, `requests` backend, a fresh engine per search, 57 searches over three queries at offsets 0-30 in steps of 5, each sweep repeated 2-3 times a few minutes apart. Every search returned 200 with no CAPTCHA or block.
  - A bare offset works: `/search?q=<q>&start=N`, with none of the footer's session tokens, returns a page past the first, and the footer marks the expected page as current. Decision 5 holds: pages can be fetched independently.
  - `start` is a result offset, not a page number. The footer's current page is `ceil(start / 10) + 1` (`start=5` shows page 2, `15` page 3, `25` page 4), but the results slide with the offset: placed in the list built from the canonical pages (`start=0,10,20,30`), the first result at `start=5` sits about 3-4 places in, at `15` about 12-16, at `30` about 19-27. It runs a few places below `start` because page 1 carries only 7-9 `general` rows; other components take the remaining slots.
  - The footer's page links keep an off-boundary offset's phase: a `start=15` page links to `start=5` and `start=25` (and `0` for page 1), so following "next" from such a page stays off the boundary.
  - Pages past the first are not stable between fetches. At a fixed offset, the first `general` result differed between rounds in most cases past page 1; page 1 was mostly stable. The `start=10` page's `general` set had a Jaccard similarity of 0.11-0.54 across rounds. Offsets 5 apart, which would share 5 results under a stable ranking, shared 1-6. Some first results at an offset appeared on none of the same round's canonical pages.
  - One sweep of the canonical pages `start=0,10,20,30` gave 37-39 `general` rows, 2-5 of them repeated on more than one page. Results that fell between pages and appeared on none cannot be counted from this test.
  - Implications: decision 2 stands (a raw `start`), but the docstring should say that a multiple of 10 lands on a page boundary and any other value slides the window. A multi-page helper (decision 4's follow-up) should step by 10 and dedupe across pages on `(title, cite)`, since `/goto` hrefs differ per render; its output is a sample of the top results, not one consistent ranking. Decision 6 stands: a cross-page rank would imply a consistency the pages do not have.
  - Not covered: deep offsets (`start=50` to `90`) and short or empty pages, `filter=0`, block rate under paging volume, the patchright backend, and whether page SERPs add new `unknown` families.
