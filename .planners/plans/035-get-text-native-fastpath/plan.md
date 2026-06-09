---
id: 35
slug: get-text-native-fastpath
status: done
branch: claude/new-benchmark-PMegd
created: 2026-06-01T07:31:21Z
concluded: 2026-06-01T14:13:24Z
pr: https://github.com/gitronald/WebSearcher/pull/145
---

# `get_text` native-`text()` fast path (post-selectolax benchmark)

A fresh benchmark of the current parse pipeline (the first since the selectolax
native rewrite in plan 026 and the parser additions in plans 027-034) found that
the pure-Python `get_text` fragment walker had become the single largest
*optimizable* cost. This plan records that benchmark and a byte-identical fast
path that recovers ~7% of `parse_serp` latency.

Methodology follows plan 023: per-SERP median + MAD, gate on the run-to-run noise
floor, and only trust **back-to-back same-session A/B** numbers (never chain
deltas across sessions or machines).

## Environment

`scripts/bench_parse.py` now records the interpreter at the top of every run
(`platform.python_version()` / implementation / platform + `WebSearcher`
version) -- parse timings are only comparable within one Python build, and the
repo's pinned `.python-version` (`3.14.0rc2`) currently can't import the package
(`pydantic 2.13.4` vs the 3.14 RC `typing._eval_type` signature). All numbers
below are **Python 3.13.12, CPython, linux**, fixture corpus
`tests/fixtures/serps.json.bz2` (87 SERPs).

## Baseline benchmark (current HEAD)

`bench_parse.py --iterations 10 --runs 3`:

- median **39.5 ms/SERP**, MAD 13.6 ms; min 17.3 / p90 75.7 / max 115.7 ms
- corpus 3760.6 ms/pass; inter-run MAD 5.7 ms -> **noise floor ~0.3%** (idle box).

cProfile (`--profile`, 870 parses, 52.6 s, tottime) top buckets:

| Frame | self | nature |
|---|---|---|
| `make_soup` (lexbor parse) | 10.5 s (20%) | structural -- one parse/SERP, unavoidable |
| `_iter_text_fragments` (get_text walker) | 5.8 s; 9.6 s cum (**18%**) | pure-Python, hot -- the target |
| `_ComponentSignals.__init__` | 5.3 s; 6.9 s cum (13%) | pure-Python (one `css('*')` walk/component) |
| `_extract_from_html` (serp-features regex) | 2.0 s | |
| `_get_dom_positions` | 1.9 s | |

`get_text` is called ~176x/parse (153,580 over 870), each walking a subtree via a
Python stack of `.iter()` generators -- 824k fragment visits, 5.4M `next()` calls.

## The fast path

Plan 026 flagged native selectolax `.text()` as the next lever but "unsafe"
because (a) native includes `script`/`style`/`template` text (the walker skips
those subtrees) and (b) native `strip=True` keeps empty fragments (the walker
drops them). Both differences are **observable only under specific conditions**,
and outside them native C `text()` is byte-identical:

- (a) vanishes when the subtree has no `script`/`style`/`template`.
- (b) vanishes when `separator == ""` (an empty fragment adds nothing to a
  `""`-join, so kept-vs-dropped is invisible) **or** `strip is False` (both keep
  empties identically).

So `get_text` delegates to `node.text(deep=True, separator=sep, strip=strip)`
when `(separator == "" or not strip)` and the subtree holds no
script/style/template (one `css_first("script,style,template")` C probe); every
other call keeps the Python walker. The only call signature that always stays on
the walker is `strip=True` with a non-empty separator (`get_text(x, " ",
strip=True)`, 38 sites) -- exactly the drop-empties-with-visible-separator case.

**Correctness verification.** Over the full corpus (315,095 element nodes, 95.2%
fast-path-eligible) every fast-pathable signature -- `("", False)`, `("", True)`,
`(" ", False)`, `("<|>", False)` -- produced **0 mismatches** against the walker.
The snapshot suite stays green without updates (`uv run pytest`: 336 passed, 4
skipped, **87 snapshots unchanged**).

## Result (back-to-back A/B, same machine state)

Stash/pop A/B with `--iterations 10 --runs 3`:

| Metric | Baseline | Fast path | Delta |
|---|---|---|---|
| Corpus total | 3872.0 ms | 3590.3 ms | **-7.3%** |
| Per-SERP median | 39.9 ms | 36.7 ms | **-8.0%** |

Far above the ~0.4-0.5% noise floor. Post-change profile: `_iter_text_fragments`
self 5.8 -> 2.2 s, cum 9.6 -> 3.5 s, fragment visits 824k -> 276k (the remainder
is the `strip=True`/non-empty-sep walker, script-bearing subtrees, and
`has_text`/`knowledge_box`); the displaced work moved into lexbor's C `text()`.

## Left for follow-up

`_ComponentSignals.__init__` is now the #2 pure-Python cost (~5 s self, ~13%): one
`css('*')` walk per component building class/id/tag presence sets. A shared scan
feeding both it and `_get_dom_positions`/`reorder_by_dom_position` (each of which
also `css('*')`-walks) is the next structural lever -- deferred to keep this
change small and byte-identical.
