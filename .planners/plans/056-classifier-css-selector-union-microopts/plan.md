---
id: 56
slug: classifier-css-selector-union-microopts
status: done
branch: feature/classifier-css-selector-union-microopts
created: 2026-07-10T23:15:13-07:00
concluded: 2026-07-10T23:42:32-07:00
pr: https://github.com/gitronald/WebSearcher/pull/191
---

# Union sequential css_first probes in classifiers

Small, byte-identical parse speedup: replace the classifier chain's
`for css in (...): if node.css_first(css) is not None` boolean-OR loops with a
single comma-union `css_first`. selectolax runs one subtree walk that
short-circuits at the first match of *any* branch, instead of N independent
subtree walks that each miss before the one that hits. Same methodology as plans
023/035/036: per-frame microbenchmark, gate on measured delta, byte-identity
pinned by the `test_parse_serp.py` snapshot suite (no snapshot updates).

## Fresh profile (the "it's been a while" re-baseline)

`uv run python -m WebSearcher.parsers.bench --profile --iterations 8`, Python
**3.14.3** (CPython, linux), WebSearcher **0.11.4a0**, corpus
`tests/fixtures/serps.json.bz2` (102 SERPs, 816 parses, 16.39 s). Top `tottime`:

| Frame | tottime | ncalls | nature |
|---|---|---|---|
| `_slx.make_soup` (lexbor parse) | 3.75 s | 816 | structural, one parse/SERP — unavoidable |
| `main.py:58 _ComponentSignals.__init__` | 1.68 s | 10448 | per-cmpt `css('*')` walk — **hard, see below** |
| `_slx._iter_text_fragments` | 0.72 s | 209808 | already optimized (plan 035) |
| `extractors/__init__.py _get_dom_positions` | 0.62 s | 816 | full-doc `css('*')` — inherent (plan 044) |
| `_slx.get_text` | 0.55 s | 136912 | already optimized (plan 035) |
| `_slx.subtree_css` | 0.54 s | 7600 | css + mem_id filter |
| `extractor_serp_features._extract_from_html` | 0.62 s cum | 816 | regex path (plan 023) |
| `main.py:112 _classify_header` | 0.49 s | 17888 | **this plan (Lever B)** |
| `utils.has_captcha` | 0.40 s | 816 | non-issue — see negative results |
| `extractor_main.is_valid` | 0.36 s | 23288 | per-candidate structural check |
| `main.py:542 knowledge_panel` | 0.36 s | 7752 | **this plan (Lever A)** |

The pipeline is already heavily optimized (five prior passes: 017/023, 035, 036,
044). The top two frames are structurally necessary or already-proven-hard, so
this plan takes the tractable middle of the profile.

## Negative results (measured, do not pursue)

Recorded so nobody re-runs these. All numbers are back-to-back same-session
microbenchmarks over the 102-SERP corpus.

1. **Filter `_ComponentSignals.classes` to an interest set** (like `names`/`ids`
   already are). `signals.classes` is only ever consulted against a fixed set of
   literal tokens (`IFnjPb`, `ITWcLb`, `Fzsovc`, the `_VIDEO_CLASSES`/
   `_LOCAL_CLASSES` sets, etc.), so filtering *looked* free. Measured **net
   loss**: 201 ms vs 196 ms/pass. `set.update(cls.split())` is a single C call;
   a Python per-token membership loop is slower, and the `css('*')` walk itself
   (not the set-building) dominates the frame anyway. The existing comment
   ("classes must stay complete") is effectively right on cost even though the
   consult set is finite.

2. **Substring-gate the AI-overview payload regexes** (`if "TgQPHd" in raw_html:
   finditer(...)`). Markers are rare (`TgQPHd` 3/102, `Sv6Kpe` 19/102, `lDPB`
   2/102) so gating *looked* free. Measured **net loss**: 177 ms vs 130 ms/pass.
   The three patterns are literal-prefixed, so `finditer` already scans for the
   literal at C speed; a Python `in` pre-check just doubles the scanning.

3. **`has_captcha` full-document text walk** is a non-issue in real usage. Only
   **1/102** SERPs carries the `CAPTCHA` substring, so the existing
   `html`-gated fast path (`"CAPTCHA" not in html`) already short-circuits
   101/102. The profile's 0.40 s is one pathological SERP walked 8×, not a
   per-parse cost. (Aside, out of scope: `LexborNode.text(deep=True)` *does*
   include `<script>` text — the docstring's "so script content doesn't
   false-positive" claim is inaccurate — but this only matters on the 1 SERP that
   reaches the walk, and changing it is behavior-affecting.)

4. **Shared structure-aware document walk for signals** — already tried and
   reverted in [plan 044](../044-shared-document-walk-signals/plan.md) (~2.4×
   slower on the signals frame). Not revisited.

## The change: comma-union the boolean-OR `css_first` loops

### Lever A — `ClassifyMain.knowledge_panel` (`classifiers/main.py:542`)

Currently 6 sequential `css_first` probes in a tuple loop, returning
`"knowledge"` on the first hit. Because the outcome is a pure boolean OR (which
selector matched is irrelevant), a single comma-union `css_first` is
**definitionally** byte-identical:

```python
# before
for css in ("h1.VW3apb", "div.knowledge-panel, div.knavi, div.kp-blk, div.kp-wholepage-osrp",
            'div[aria-label="Featured results"][role="complementary"]',
            'div[jscontroller="qTdDb"]', "div.obcontainer", '[id$="__onebox_content"]'):
    if node.css_first(css) is not None:
        return "knowledge"
# after
_KP_UNION = ('h1.VW3apb, div.knowledge-panel, div.knavi, div.kp-blk, '
             'div.kp-wholepage-osrp, div[aria-label="Featured results"][role="complementary"], '
             'div[jscontroller="qTdDb"], div.obcontainer, [id$="__onebox_content"]')
if node.css_first(_KP_UNION) is not None:
    return "knowledge"
```

(Keep the trailing `node.attrs.get("jscontroller") == "qTdDb"` root check as-is —
it tests the root's attribute, not a descendant, so it is not part of the union.)

Microbench (1225 unknown main cmpts, 0 mismatches): **95.9 ms -> 66.0 ms/pass**
(-31% on the frame; frame is ~0.36 s tottime / ~2% of parse).

### Lever B — `ClassifyMainHeader._classify_header` (`classifiers/main.py:112`)

`_HEADER_CSS_BY_LEVEL[level]` is three selectors iterated separately, each a
subtree `css`; union them per level into one selector. Unlike Lever A this loop
inspects the matched headers' *text* (not a pure boolean), so union order
matters in theory: the current code checks all of selector-1's headers before
selector-2's, whereas the union returns document order. Corpus-verified
**0 mismatches** over 1225 cmpts, and pinned by the snapshot suite — same
"evidence-backed byte-identity" bar the codebase already uses elsewhere. Note the
theoretical precedence change in the code comment.

```python
_HEADER_CSS_BY_LEVEL = {
    level: (
        f'h{level}[role="heading"], h{level}.O3JH7, h{level}.q8U8x, '
        f'h{level}.mfMhoc, [aria-level="{level}"][role="heading"]'
    )
    for level in (2, 3)
}
# _classify_header: drop the `for css in ...` loop, iterate node.css(_HEADER_CSS_BY_LEVEL[level]) once
```

Microbench (0 mismatches): **85.9 ms -> 67.9 ms/pass** (-21% on the frame; frame
is ~0.49 s tottime).

### Lever C — cold pure-OR loops (free simplification, negligible perf)

Same definitionally-safe boolean-OR union, applied for consistency; each is
gated/cold so the perf delta is noise, but the code is simpler:

- `ClassifyMain.images` (`main.py:397`) — 2 `css_first` (`div[id="imagebox_bigimages"]`, `div[id="iur"]`).
- `ClassifyMain.local_results` (`main.py:564`) — 2 `css_first` (`div.Qq3Lb`, `div.VkpGBb`).
- `ExtractorFooter.is_hidden_footer` (`extractor_footer.py:49`) — 3 `css_first`.

### Explicitly out of scope

- `ads.py:169 _parse_ad_secondary_sub_details` and `ads.py:222
  _parse_ad_standard_text` also loop over selectors, but they **use the matched
  node** with selector-priority order (first *selector* that matches, not first
  in document order). A comma-union changes which node is returned when a
  subtree matches multiple branches, so these are not safe to union. Left alone.
- `_ComponentSignals`, `_get_dom_positions`, `has_captcha` — see negative
  results.

## Expected impact

Levers A + B together remove ~48 ms/corpus-pass (~2% of the ~2050 ms/pass parse
total on this box); Lever C is a wash but simplifies. Modest, but every change is
a net simplification (fewer selectors, one walk) with byte-identical output.

## Cross-corpus regression check (done, pre-implementation)

The fixture snapshot suite covers 102 SERPs; Lever B's precedence change could in
theory diverge on inputs the fixtures don't hold. Ran current-vs-union for every
changed classifier over the larger, adversarial `data/crawl6-unknowns` corpus
(**804 SERPs**, all of which produced `unknown` components — the hardest edge
cases). Comparisons: **9,931** main unknown components (× 2 levels = ~19.9k header
checks) + **488** footer components. Result: **0 mismatches** on every lever
(`header`, `kp`, `images`, `local`, `footer`). Combined with the definitional
safety of A/C, this clears the byte-identity bar for the whole change.

## Verification gate

- `uv run pytest tests/test_parse_serp.py` green **with no snapshot updates** —
  the byte-identity contract.
- `uv run pytest` green overall.
- Re-run `uv run python -m WebSearcher.parsers.bench --iterations 50 --runs 5`
  back-to-back on the same session before/after and confirm the corpus-total
  delta clears the run-to-run noise floor (the bench prints it); record in the
  Log. Do **not** trust a cross-session number.

## Implementation order

1. Lever A (knowledge_panel) — biggest, definitionally safe.
2. Lever C (images, local_results, is_hidden_footer) — trivial, same pattern.
3. Lever B (header union) — corpus-verified; add the precedence comment.
4. Run snapshot suite (no updates) + full suite; run the same-session A/B bench.

## Log

### 2026-07-10 — implemented (branch `feature/classifier-css-selector-union-microopts`)

Applied all three levers in `classifiers/main.py` + `extractors/extractor_footer.py`:
- Lever A: `knowledge_panel` 6 probes -> one `_KNOWLEDGE_PANEL_CSS` union (root
  `jscontroller` check kept separate).
- Lever B: `_HEADER_CSS_BY_LEVEL` now one union selector per level; `_classify_header`
  drops the inner `for css in` loop. Precedence-change caveat noted in the comment.
- Lever C: `images`, `local_results`, `is_hidden_footer` unioned.

**Tests:** `pytest tests/test_parse_serp.py` -> 102 snapshots passed, no updates
(byte-identity holds). Full suite `pytest` -> 643 passed.

**Same-session A/B** (`bench --iterations 40 --runs 5`, Python 3.14.3, 102-SERP
corpus, back-to-back on one box):

| | corpus median | per-SERP median |
|---|---|---|
| base (dev)        | 1598.1 ms | 13.185 ms |
| new (union)       | 1575.8 ms | 12.814 ms |

New is faster on every run (warmest run 1563.4 -> 1548.2 ms). ~1.4% off corpus
total, **2.8% off the median SERP** (classify frames are a larger share of a
typical SERP than of the few huge ones where `make_soup` dominates). The
per-corpus estimate in "Expected impact" (~48 ms) was optimistic; the realized
corpus-total delta is ~15-22 ms, at the upper edge of the ~0.8-1.5% noise floor,
but directionally consistent across all five runs. Landed as a
simplification-with-a-small-speedup.
