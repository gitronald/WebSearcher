---
status: active
branch:
needs: [a]
---

# Study the selectolax 1.0 release notes for our use

Part of [Upgrade selectolax to 1.0](../plan.md).

## Plan

Read the 1.0.0 release notes, and the 0.4.11-0.4.13 notes that step a pulls in,
against how WebSearcher actually uses selectolax. Classify every item, so c knows
what to change and d knows what to watch.

Sources: <https://github.com/rushter/selectolax/releases> (v0.4.11, v0.4.12,
v0.4.13, v1.0.0). Read them with
`gh release view <tag> -R rushter/selectolax --json body -q .body`.

### Classification

Each release-note item gets one label, with the call sites that justify it:

| Label | Meaning |
|---|---|
| n/a | we do not use the API it touches |
| free | we use it and gain without a code change (a speedup, a crash fix) |
| watch | we use it and its output may change; d checks it against the snapshot suite |
| adopt now | a small change in our code that the snapshot suite covers; c does it |
| follow-up | worth doing, but needs a parser refactor; a later plan does it |

The table goes in a `## Findings` section of this file, with one row per item.

### Checks to run

Cite the command or the `file:line` for each finding.

- **Removed APIs.** Confirm nothing in `WebSearcher/`, `tests/`, or
  `.claude/skills/` imports `selectolax.parser` (Modest) or calls
  `parse_fragment()`. Every import should be `selectolax.lexbor`.
- **Fragments.** We never pass `is_fragment=True`; `reparse_fragment` in
  `WebSearcher/_slx.py` re-parses a full document and takes `body`'s first
  element. Check whether the `head`/`body`/`root` staleness fixes touch that path
  (`notices.py` is its only caller).
- **Text.** `_slx._node_text` (`text(deep=False)`) and `_slx.get_text`
  (`text(deep=True, separator=..., strip=...)`) are the hot text paths. Check
  whether any caller passes `skip_empty`, whether the fixtures contain bytes that
  would now become U+FFFD, and how much of the a profile the 5x `text()` speedup
  can reach.
- **Attributes.** Find every `attrs`/`attributes` read that could see a namespaced
  attribute (`xlink:href` on SVG `<use>`), and count them in the corpus:
  `uv run python` over `tests/fixtures/serps.json.bz2`, counting `xlink:` in the
  stored HTML. Note where `attrs.items()`/`.values()` are used (now faster).
- **Mutation and iteration.** List the helpers and parsers that remove, unwrap, or
  decompose nodes, or iterate while mutating, against the `iter()` and `unwrap()`
  fixes.
- **Node equality.** Find `==` comparisons of nodes (for example in the
  `subtree_first`/`subtree_css` self-exclusion), which gain from the faster
  `__eq__`.
- **Selector helpers.** Note any use of `css_matches`, `any_css_matches`,
  `scripts_contain`, `script_srcs_contain`, `select()`, `traverse()`,
  `merge_text_nodes()`, or `text_lexbor`.
- **Workarounds that become dead.** Look for `UnicodeDecodeError` handling or other
  guards around selectolax quirks that 1.0.0 fixes upstream.
- **Typing.** Diff the shipped `.pyi` stubs between 0.4.13 and 1.0.0 for signature
  changes that pyrefly's strict preset would flag.
- **Wheels.** Confirm PyPI has 1.0.0 wheels for cp312, cp313, and cp314 on linux,
  macOS, and Windows, matching the CI matrix.
- **New API.** Assess `LexborHTMLParser(..., encoding=True)` against how
  `make_soup` receives `bytes`.

### Done when

The Findings table covers every item in the four releases' notes. Each `adopt now`
row names the change for c, each `watch` row names the component types for d to
inspect, and each `follow-up` row is listed in the umbrella's Log as a candidate
plan.

## Findings

Checked against `feature/selectolax-1-0-upgrade` at `0.11.7a1`. Release notes read with
`gh release view <tag> -R rushter/selectolax --json body -q .body`. Corpus counts come
from `tests/fixtures/serps.json.bz2` (102 SERPs, every `html` a `str`), by the probe
below.

### Checks

- **Removed APIs.** `grep -rn "selectolax.parser\|parse_fragment\|is_fragment" WebSearcher tests .claude/skills`
  finds only our own `_slx.reparse_fragment` and its one caller (`notices.py:79`). Every
  import is `selectolax.lexbor` (`_slx.py:35-36` plus the `LexborNode` imports in the
  parsers, extractors and classifiers). Nothing does a bare `import selectolax`, so the
  0.4.13 change to what `import selectolax` pulls in does not reach us.
- **Fragments.** We never pass `is_fragment=True`. `reparse_fragment` (`_slx.py:157`)
  parses a full document and returns `parser.body`'s first element; it never removes
  `<head>`/`<body>` or sets `inner_html`, so the `head`/`body`/`root` staleness fixes do
  not reach it. `notices.py:83` then calls `remove(recursive=False)` on a node of the
  re-parsed document, not of a fragment.
- **Text.** No caller passes `skip_empty` (`grep -rn skip_empty WebSearcher` is empty).
  `_node_text` (`_slx.py:44`) is the one `deep=False` call. The corpus has 0 U+FFFD
  characters and 0 lone surrogates, and `make_soup` hands lexbor a `str` (bytes are
  decoded with `errors="replace"` first, `_slx.py:93`), so the U+FFFD substitution
  changes cannot fire on our input.
- **Attributes.** 0 `xlink:` occurrences in the corpus. The only colon-named attribute
  lexbor reports is `wiz:wakeup` (15, all on HTML `div`s); qualified-name reporting only
  differs for attributes adjusted in foreign (SVG/MathML) content. No parser reads attrs
  from `svg`/`use` elements. No `attrs.items()`/`.values()` iteration in `WebSearcher/`;
  reads are `.attributes.get(...)`/`.attrs.get(...)` lookups (125 sites).
- **Mutation and iteration.** `decompose()` at `general.py:118` and `ai_overview.py:149`
  loops over a list built first (`list(top_menu.iter(...))`, `elem.css(...)`), not a live
  `iter()`. `remove(recursive=False)` detaches subtrees at `extractor_main.py:161,168,175`
  (ads), `extractor_rhs.py:23` (RHS panel) and `notices.py:83`; the detached subtrees are
  then walked. No `unwrap`, `strip_tags`, `unwrap_tags`, `inner_html` setter, or `clone`.
- **Node equality.** No `==` between nodes; `subtree_first`/`subtree_css`/
  `walk_descendants` and the sibling helpers compare `mem_id` (`_slx.py:181-262`), so the
  faster `__eq__` does not reach us.
- **Selector helpers.** No use of `css_matches`, `any_css_matches`, `scripts_contain`,
  `script_srcs_contain`, `select()`, `traverse()`, `merge_text_nodes()`, `text_lexbor`,
  `text_content`, or `attribute_longer_than`.
- **Dead workarounds.** The one `UnicodeDecodeError` handler
  (`_ai_overview_payloads.py:73`) guards Python's `unicode_escape` codec, not selectolax.
  None dead.
- **Typing.** `lexbor.pyi` diff 0.4.13 -> 1.0.0: `DefaultT` renamed `_DefaultT`
  (we do not import it), `Optional[str]` -> `str | None`, removed `__repr__` stubs, and
  the new `encoding: bool = False` on `LexborHTMLParser.__init__`. `parser.pyi` is gone.
  Nothing we call changed signature; pyrefly confirms in c.
- **Wheels.** PyPI 1.0.0 has cp312, cp313 and cp314 wheels for manylinux, musllinux,
  macOS and Windows (82 files; `requires_python >=3.9,<3.16`), matching CI's 3.12-3.14.
- **New API.** `make_soup` accepts `bytes` and decodes as UTF-8 with replacement.
  `LexborHTMLParser(..., encoding=True)` would detect a non-UTF-8 encoding instead. Every
  in-repo caller passes `str`; changing bytes handling changes output for non-UTF-8
  input, so it is a follow-up.
- **`skip_empty` (tested, not adoptable as is).** Under 1.0.0 the existing `get_text`
  fast path still equals the Python walker on all 323,168 eligible element nodes for
  `(sep, strip)` in `("", True)`, `(" ", False)`, `("", False)`. Native
  `text(deep=True, separator=s, strip=True, skip_empty=True)` differs from the walker's
  strip-then-drop-empties path on 5,841 of 323,168 nodes (1.8%) for both `" "` and `"|"`:
  `skip_empty` drops only nodes that are all ASCII whitespace, while `str.strip()` also
  empties nodes of non-ASCII whitespace (`&nbsp;` and similar), which then add an empty
  part (`'0+|Free'` vs `'0+||Free'`, `'es.'` vs `'es.|'`). Repeat with the probes
  committed beside this plan:

  ```bash
  uv run --no-project --with selectolax==1.0.0 --with orjson python .planners/plans/059-selectolax-1-0-upgrade/skip_empty_059.py
  uv run --no-project --with selectolax==1.0.0 --with orjson python .planners/plans/059-selectolax-1-0-upgrade/skip_empty_diff_059.py
  ```

- **Profile reach.** Cython calls carry no profile frames, so selectolax time lands in the
  caller's `tottime`. In the 0.4.13 profile (059a Log) lexbor parsing is `make_soup`
  (9.49 of 39.2 s); `text()` runs inside `get_text` (1.21 s), `has_captcha` (0.99 s, one
  whole-document `text()`), and `_iter_text_fragments` (1.79 s, per-node
  `text(deep=False)`). The 5x `text()` speedup can reach at most that ~4 s (about 10%),
  and less, since those totals include our own Python work.

### Classification

| Release | Item | Label | Why / call sites |
|---|---|---|---|
| 0.4.11 | NULL checks in CSS selectors module | free | crash guard; every parser calls `css`/`css_first` |
| 0.4.11 | html5test pretty-print serialization fix | n/a | we never call `html_pretty` |
| 0.4.11 | Update lexbor | watch | parser output; covered by the snapshot suite (passed on 0.4.13, 059a) |
| 0.4.12 | `options` parameter on `LexborHTMLParser` | n/a | not used; possible follow-up only if parse time needs it |
| 0.4.12 | `clone()` losing nodes for empty fragments | n/a | no `clone` |
| 0.4.12 | empty elements in `text_lexbor` | n/a | no `text_lexbor` |
| 0.4.12 | Update lexbor | watch | as 0.4.11 |
| 0.4.13 | lexbor-only builds (`--disable-modest`) | n/a | build option |
| 0.4.13 | `import selectolax` no longer imports submodules | n/a | we import `selectolax.lexbor` directly everywhere |
| 0.4.13 | Update lexbor | watch | as 0.4.11 |
| 1.0.0 | Remove Modest; `selectolax.parser` raises `ImportError` | n/a | not imported; downstream note in CHANGELOG (c) |
| 1.0.0 | Remove `parse_fragment()` | n/a | not used |
| 1.0.0 | `css_matches`/`any_css_matches` fragment scope | n/a | not used |
| 1.0.0 | `tags`/`strip_tags` on fragments | n/a | not used |
| 1.0.0 | fragment `<html>` wrapper reported as a match | n/a | no fragments |
| 1.0.0 | `scripts_contain`/`script_srcs_contain` fragment scope | n/a | not used |
| 1.0.0 | `scripts_contain`/`script_srcs_contain` cache keyed by root | n/a | not used |
| 1.0.0 | `select()` fragment scope | n/a | not used |
| 1.0.0 | `traverse()` fragment coverage | n/a | not used (`walk_descendants` uses `css("*")`) |
| 1.0.0 | `attribute_longer_than` consistency | n/a | not used |
| 1.0.0 | `attrs`/`attributes` report qualified names | watch | 125 `.attributes`/`.attrs` reads; corpus has 0 `xlink:`, only `wiz:wakeup` on HTML divs; d checks every component type via snapshots |
| 1.0.0 | `iter()` skipping children after removal mid-iteration | n/a | removals loop over prebuilt lists (`general.py:118`, `ai_overview.py:149`) |
| 1.0.0 | fragment starting with text drops the rest | n/a | no fragments |
| 1.0.0 | `text()` raising instead of truncating on collect failure | free | all `text()` paths; no output change expected |
| 1.0.0 | `scripts_contain` wrong after mutation | n/a | not used |
| 1.0.0 | undecodable bytes -> U+FFFD in `html`/`attrs`/`id`/`tag`/... | n/a | input is always `str` (corpus: 0 U+FFFD, 0 surrogates) |
| 1.0.0 | `text_lexbor` memory | n/a | not used |
| 1.0.0 | `merge_text_nodes()` faster | n/a | not used |
| 1.0.0 | faster `__eq__` | n/a | we compare `mem_id`, never nodes |
| 1.0.0 | faster `attrs.items()`/`.values()` | n/a | no iteration over attrs |
| 1.0.0 | `inner_html` setter on non-elements | n/a | no setter use |
| 1.0.0 | `head`/`body` dangling after `inner_html` on `<html>` | n/a | no setter use |
| 1.0.0 | `inner_html` setter freeing replaced children | n/a | no setter use |
| 1.0.0 | `root` stale on fragments | n/a | no fragments |
| 1.0.0 | segfault walking a detached fragment root | watch | we walk detached subtrees after `remove(recursive=False)` (`extractor_main.py:161,168,175`, `extractor_rhs.py:23`, `notices.py:83`); they are document nodes, not fragments; d checks ad, shopping_ads, knowledge_rhs, and notice snapshots |
| 1.0.0 | avoid segfaults on OOM | free | robustness |
| 1.0.0 | `text` up to 5x faster (raw-byte concatenation) | watch | `get_text` fast path, `has_captcha`, `_node_text`; up to ~10% of profiled time; d measures; byte output checked by the snapshot suite and the probe above (fast path still identical) |
| 1.0.0 | `skip_empty` honored by `text(deep=True)` | follow-up | could move `get_text`'s strip+separator path native, but differs on 1.8% of nodes (non-ASCII whitespace); needs a native-plus-filter design and its own byte-identity proof |
| 1.0.0 | `text(deep=False)` substitutes U+FFFD | n/a | `str` input, no undecodable bytes |
| 1.0.0 | `id` on text nodes | n/a | `el.id` read on elements only (`classifiers/main.py:72`) |
| 1.0.0 | `attrs[key] = value` raises `TypeError` | n/a | no attribute writes |
| 1.0.0 | no segfault constructing `LexborNode`/`LexborAttributes` directly | n/a | never constructed directly |
| 1.0.0 | `unwrap()` corrupting the tree | n/a | no `unwrap` |
| 1.0.0 | `head`/`body` stale after removing `<head>`/`<body>` | n/a | `reparse_fragment` reads `body` without removing it |
| 1.0.0 | `attrs` reading freed memory | free | memory safety; we read `attrs` only while the node is alive |
| 1.0.0 | leak in `attrs[key] = None` | n/a | no attribute writes |
| 1.0.0 | possible leak in `clone()` | n/a | no `clone` |
| 1.0.0 | `encoding=True` on `LexborHTMLParser` | follow-up | `make_soup` decodes bytes as UTF-8 with replacement (`_slx.py:93`); detection would change output for non-UTF-8 bytes; all in-repo callers pass `str` |

**For c:** no `adopt now` items. c is the bare upgrade, the CHANGELOG entry, and the
prerelease bump.

**For d (watch):** lexbor update output (all types, via snapshots); `attrs` qualified
names (all types); detached-subtree walks in ad, shopping_ads, knowledge_rhs and notices
components; `text()` speed in `get_text`/`has_captcha`/`_iter_text_fragments` frames.

**Follow-up candidates (for the umbrella Log):** native `skip_empty` text path for
`get_text`'s strip+separator case; `encoding=True` for `bytes` input to `make_soup`.

## Log
