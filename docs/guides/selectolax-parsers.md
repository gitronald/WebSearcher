# Building component parsers on selectolax

WebSearcher's parser pipeline runs on [selectolax](https://github.com/rushter/selectolax)'s lexbor backend. The bs4 + lxml era ended with plan [026](../plans/026-selectolax-parser-backend-exploration.md); per-SERP parse time dropped ~3.4× (122 ms → 36 ms median). This guide captures the working patterns for new parsers and the bs4-vs-selectolax semantic gaps that bit us during the migration.

## API surfaces

Two layers, in order of preference:

1. **Native `selectolax.lexbor` (`LexborNode`)** — the C-backed CSS engine, attribute view, tree walks. Use this whenever the semantics match what you need.
2. **`WebSearcher._slx`** — a thin helper module for the ~10 bs4 behaviors that selectolax doesn't replicate natively (text-fragment iteration, descendants-only CSS, text-inclusive sibling walks, etc.). Re-uses lexbor under the hood.

`WebSearcher.utils` no longer wraps node operations — its surface is now `make_soup`, `has_captcha`, `slugify`, file/URL helpers, `SSH`. Reach for `_slx` or native methods directly.

## Parser shape

A component parser receives the component's root `Node` (called `cmpt` for legacy reasons) and returns a list of dicts:

```python
from selectolax.lexbor import LexborNode as Node

from .._slx import get_text


def parse_my_component(cmpt) -> list:
    node: Node = cmpt
    title = node.css_first("h3")
    link = node.css_first("a")
    return [{
        "type": "my_component",
        "sub_rank": 0,
        "title": get_text(title, " ", strip=True) if title is not None else None,
        "url": link.attrs.get("href") if link is not None else None,
    }]
```

Register the parser in `WebSearcher/component_parsers/__init__.py` and add a classifier branch in `WebSearcher/classifiers/main.py`.

## The bs4-vs-selectolax semantic landmines

Every one of these caused a snapshot regression during the migration. Memorize them.

### 1. `node.css(...)` matches `node` itself

```python
# bs4
cmpt.find("div", class_="VkpGBb")     # descendants only

# selectolax
cmpt.css("div.VkpGBb")                # may return cmpt as first result if cmpt matches!
```

Use `_slx.subtree_first` / `subtree_css` for descendants-only semantics, or filter inline:

```python
from .._slx import subtree_first, subtree_css

inner = subtree_first(cmpt, "div.VkpGBb")
businesses = subtree_css(cmpt, "div.rllt__details")
```

### 2. `node.traverse(...)` walks the entire document, not the subtree

`traverse` continues forward through the document past the node's subtree. **Never use it on a component node.** Use `_slx.walk_descendants(node)` (backed by `node.css('*')`) for subtree pre-order, or iterate `node.iter(include_text=False)` for direct children only.

### 3. Comma selectors in `.css(...)` are tag-grouped, not document-order

```python
# bs4 walks document order
cmpt.find_all(["span", "div", "a"])

# selectolax returns spans first, then divs, then a's
cmpt.css("span, div, a")
```

When document order matters, use `walk_descendants` + a tag check:

```python
matches = [n for n in walk_descendants(cmpt) if n.tag in ("span", "div", "a")]
```

### 4. `.attributes` allocates a fresh dict per call; prefer `.attrs`

```python
# 4x slower (allocates a dict every time)
cls = el.attributes.get("class")

# A non-allocating view
cls = el.attrs.get("class")
```

For element IDs, `el.id` is faster than `el.attrs.get("id")`. This matters in hot loops (the classifier signal-builder walks every element of every component).

### 5. `class` is a single string, not a list

```python
# bs4
if "promo" in tag["class"]:           # list contains check

# selectolax: tag.attrs.get("class") is "promo  banner   highlighted"
from .._slx import class_tokens
if "promo" in class_tokens(tag):
```

For exact multi-token class matching (bs4's `class_="mnr-c pla-unit"` semantics — order-sensitive!), compare lists directly: `class_tokens(tag) == ["mnr-c", "pla-unit"]`. The CSS `~=` operator does **not** mean exact-multi-token.

### 6. `Node.text(strip=True)` keeps empty fragments

bs4's `get_text(strip=True)` strips each fragment AND drops empties. Selectolax's native `strip=True` only strips — empty fragments stay, producing leading/trailing/extra separators that silently corrupt slugs and link keys.

Use `_slx.get_text(node, separator, strip)` for bs4-faithful behavior; it also skips `script` / `style` / `template` subtrees (selectolax doesn't).

### 7. Sibling navigation skips text nodes

bs4's `.next_sibling` is text-inclusive; selectolax's `.next` may skip text. Use `_slx.next_sibling` / `previous_sibling` / `next_siblings` for the bs4 behavior.

### 8. `Tag.string` semantics

`_slx.node_string(node)` returns the single string child (recursing through a single tag child), or `None` when the node has zero or multiple children. Use this when matching bs4's `find(string=True)` pattern (only `knowledge.py` does at present).

### 9. `copy.copy(tag)` — re-parse to detach

If you need an independent subtree (for `parser.body`-style modifications), call `_slx.reparse_fragment(node)`. It re-parses the node's outer HTML into a fresh tree.

### 10. `make_soup` accepts `str | bytes | Node`

Pass `Node` through unchanged; bytes decode as UTF-8 (replace errors). Don't re-parse already-parsed input.

## Perf patterns

These shaped the final hot path; follow them in new parsers.

### Push selection work into C

The lexbor CSS engine is dramatically faster than Python iteration. Prefer one specific CSS query over a Python loop:

```python
# Slow: Python walk
for child in walk_descendants(cmpt):
    if child.tag == "div" and "Wt5Tfe" in class_tokens(child):
        do_something(child)

# Fast: C-level CSS
for child in subtree_css(cmpt, "div.Wt5Tfe"):
    do_something(child)
```

### Avoid building a full document text string when you just need to check substrings

`soup.text(deep=True)` allocates a ~50KB string per call. For substring checks, see if you can scope to the relevant container (e.g. `cmpt.css_first("h2")`) or use the raw HTML markup (`parse_serp` publishes it via `WebSearcher.component_parsers.ai_overview.raw_serp_html` — a `ContextVar`).

### Cache document-scoped work via the `raw_serp_html` ContextVar

`parse_serp` sets `raw_serp_html` to the raw markup. Parsers that need document-wide context (like AI overview's payload extraction) read from it instead of serializing the document per call. See `_ai_overview_payloads.extract_payloads` for an `lru_cache(maxsize=2)` example.

### Don't pre-build text via `get_text` when one substring check would do

`get_text(soup)` over a large subtree is expensive (it allocates per fragment). If you're checking `"foo" in get_text(node)`, often `node.css_first("...")` against the structural marker is cheaper.

## Component identity: use `mem_id`, not `id()`

Each lexbor `Node` exposes a stable `mem_id` (int) for the underlying DOM node. `id(node)` is the Python-object identity, which is **not** stable when you re-wrap the same DOM node via `.parent` or `.css`. Use `node.mem_id` for set membership, deduplication, and equality.

## Common idioms

### Conditional get_text

```python
text = get_text(node.css_first("div.title"), " ", strip=True)
# Returns None if css_first returned None, matching the bs4-era convention.
```

### Self-excluding descendant search

```python
from .._slx import subtree_first, subtree_css

first = subtree_first(cmpt, "div.g")        # one match, descendants only
many = subtree_css(cmpt, "div.MjjYud")      # all matches, descendants only
```

### bs4 `class_=[...]` OR

CSS comma-OR matches; the doc-order caveat above only matters if you read results back as a list.

```python
header = cmpt.css_first('h2[role="heading"], h2.O3JH7, h2.q8U8x')
```

### bs4 `attrs={"id": ["bres", "brs"]}` OR

Same comma trick: `cmpt.css('div[id="bres"], div[id="brs"]')`.

## When to add a new helper to `_slx`

Only when the bs4 semantic gap isn't expressible as a 2-3 line idiom at the call site. Examples that earned their place: `walk_descendants`, `subtree_first`, `node_string`, `reparse_fragment`. Examples that didn't (and got inlined or deleted): `_build_css`, `find_text`, the bs4 `find(name, attrs)` wrapper. Always prefer letting the parser call the native `Node` API directly.

## Bench + snapshot discipline

- `tests/test_parse_serp.py` snapshots `parse_serp` output across 66 fixtures. Any change touching the parse path must keep them green.
- The `parse-bench` skill (`.claude/skills/parse-bench/bench_parse.py`) is the perf gate. Run `--iterations 5 --runs 3` and compare median ms/SERP against the baseline noted in the most recent perf commit message.
- New parser? Add the fixture (if any) to `tests/fixtures/`, regenerate snapshots once with `pytest --snapshot-update`, and verify the diff is **only** your new component's rows.

## Reference

- `WebSearcher/_slx.py` — all helpers, with rationale in each docstring.
- `WebSearcher/component_parsers/general.py` — a representative parser exercising most of the patterns above.
- `WebSearcher/classifiers/main.py` `_ComponentSignals` — the hottest selectolax usage in the codebase; demonstrates `el.attrs` + `el.id` micro-optimizations.
- `docs/plans/026-selectolax-parser-backend-exploration.md` — the migration plan with the full history (parity harness, native rewrite, perf log).
