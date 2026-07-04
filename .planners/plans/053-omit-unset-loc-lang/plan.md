---
id: 53
slug: omit-unset-loc-lang
status: draft
branch:
created: 2026-07-04T14:09:22-07:00
concluded:
pr:
---

# Omit unset loc and lang from SERP records and logs

## Plan

### Problem

`SearchEngine.search()` coerces an unset `location`/`lang` to `""` instead of
passing `None` through (`WebSearcher/searchers/searchers.py:118-119`):

```python
"loc": str(location) if location is not None else "",
"lang": str(lang) if lang is not None else "",
```

This contradicts the declared schemas — `SearchParams.loc` is `str | None = None`
(`WebSearcher/models/searches.py:17`) and `BaseSERP.loc` is `str | None = None`
with description "Location *if set*" (`WebSearcher/models/data.py:104`) — and it
defeats the JSONL formatter's null-omission (`WebSearcher/logger.py`), which
drops `None` values but keeps `""`. Observed effects:

- Saved SERP records carry `"loc": ""` / `"lang": ""` instead of `null`.
- Every JSONL search log line carries a useless `"loc": ""` key, even though the
  schema's design is "each line carries only the keys that apply".

There is **no functional impact on the search URL**: `url_params` only adds
`uule`/`hl` when the value is truthy (`WebSearcher/models/searches.py:30-32`),
so `""` and `None` build identical URLs.

### Repro (offline, no network)

```bash
uv run python -c "
from WebSearcher.models.searches import SearchParams
sp = SearchParams.create({'qry': 'x', 'loc': '', 'lang': ''})
print(sp.to_serp_output())  # loc/lang are '' rather than None
print(sp.url)               # no uule/hl either way: '' is falsy
"
```

A live capture shows the log symptom — the `ws-demo search` JSONL search line
ends with `"qry": "...", "loc": ""`.

### Fix

Pass `location` and `lang` through unchanged in `SearchEngine.search()` (drop
the `else ""` coercion; `str(...)` only when non-None). One or two lines.

### Consequences / checks

- **Output schema change (minor but user-visible):** saved records flip
  `"loc": ""` -> `"loc": null` (same for `lang`), and JSONL search lines drop
  the `loc` key entirely when unset. Needs a changelog **shape note** and a
  check that downstream dict-style consumers don't compare `loc == ""`.
- `serp_id` hashes `f"{self.qry}{self.loc}..."` plus a timestamp
  (`WebSearcher/models/searches.py:45`); the hash input changes for unset-loc
  searches, but serp_ids are already unique per call via the timestamp, so no
  compat concern — note only.
- Add/extend a test asserting the search JSONL line omits `loc` when no
  location is passed, and that a set location still round-trips.
