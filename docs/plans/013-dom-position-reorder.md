---
status: done
branch: update/extractor-position-tracking
created: 2026-02-22T12:56:12-08:00
completed: 2026-02-20T11:52:22-08:00
pr: https://github.com/gitronald/WebSearcher/pull/95
---

# DOM Position Reorder

## Context

Components are ranked by extraction order, not DOM order. The extractor runs `_ads_top()` before `_main_column()`, so ads always get lower rank numbers than ai_overview — even when Google places the ai_overview above ads in the DOM. Observed in v0.6.8a1 "best credit cards" where the DOM has ai_overview before tads, but parsed output has ads at ranks 0-3 and ai_overview at rank 4.

## Approach

Build an external position map (`id(element) -> (start, end)`) from a pre-order traversal before extraction starts, then re-sort main-section components by their effective DOM position after extraction completes. The map is keyed by `id(element)` to avoid modifying the DOM tree.

### Why not `data-ws-pos` attributes?

The original plan added `data-ws-pos` attributes directly on DOM elements. This broke two things:
1. Feature extraction that uses `regex` on `str(soup)` — extra attributes changed the serialized HTML
2. `extract_children` logic that checks `if not ch.attrs` — the injected attribute made every element appear to have attributes

Switching to an external dict keyed by `id(element)` avoids both issues.

### Ancestor detection

When a component's element is a wrapper (e.g. `div.M8OgIe` top-bar) that contains another component's element (e.g. `div#tads`), the wrapper's DOM position always precedes its descendant in pre-order traversal. Without correction, the wrapper would always sort before its children regardless of the actual layout intent.

The fix uses `(start_pos, end_pos)` ranges to detect ancestor-descendant pairs (range containment: `start <= other_start <= end`). When detected, the ancestor's effective sort position shifts to its first child element positioned after the nested component's subtree.

## Changes

### `WebSearcher/extractors/__init__.py`

- `_get_dom_positions(soup)` — pre-order traversal that maps `id(element)` to `(start_pos, end_pos)` ranges, computed before extraction starts
- `extract_components()` — calls `_get_dom_positions` before extraction and passes the result to `reorder_by_dom_position` after all handlers complete

```python
def extract_components(self):
    log.debug(f"Extracting Components {'-'*50}")
    dom_positions = self._get_dom_positions(self.soup)
    self.rhs_handler.extract()
    self.header_handler.extract()
    self.main_handler.extract()
    self.footer_handler.extract()
    self.rhs_handler.append()
    self.components.reorder_by_dom_position(dom_positions)
    log.debug(f"total components: {self.components.cmpt_rank_counter:,}")

@staticmethod
def _get_dom_positions(soup):
    """Map element id -> (start_pos, end_pos) in pre-order traversal.

    end_pos is the position of the last descendant tag, so element B is
    inside element A when A.start <= B.start <= A.end.
    """
    all_tags = list(soup.find_all(True))
    pos = {id(t): i for i, t in enumerate(all_tags)}
    end = list(range(len(all_tags)))
    for i in range(len(all_tags) - 1, -1, -1):
        parent = all_tags[i].parent
        if parent and id(parent) in pos:
            pi = pos[id(parent)]
            if end[i] > end[pi]:
                end[pi] = end[i]
    return {id(t): (i, end[i]) for i, t in enumerate(all_tags)}
```

### `WebSearcher/components.py`

- `reorder_by_dom_position(dom_positions)` — sorts main-section components by effective DOM position, preserving header/footer/rhs insertion order

```python
def reorder_by_dom_position(self, dom_positions):
    section_order = {"header": 0, "main": 1, "footer": 2, "rhs": 3}
    main_components = [c for c in self.components if c.section == "main"]

    def _effective_pos(cmpt):
        rng = dom_positions.get(id(cmpt.elem))
        if rng is None:
            return float('inf')
        start, end = rng

        for other in main_components:
            if other is cmpt:
                continue
            other_rng = dom_positions.get(id(other.elem))
            if other_rng is None:
                continue
            o_start, o_end = other_rng
            if start <= o_start <= end:
                # cmpt.elem is ancestor of other.elem — shift position
                # to first child after the nested subtree
                best = float('inf')
                for ch in cmpt.elem.children:
                    if not hasattr(ch, 'name') or not ch.name:
                        continue
                    ch_rng = dom_positions.get(id(ch))
                    if ch_rng and ch_rng[0] > o_end and ch_rng[0] < best:
                        best = ch_rng[0]
                if best != float('inf'):
                    return best

        return start

    def sort_key(cmpt):
        section_idx = section_order.get(cmpt.section, 1)
        if cmpt.section == "main":
            return (section_idx, _effective_pos(cmpt))
        return (section_idx, cmpt.cmpt_rank)

    self.components.sort(key=sort_key)
    for i, cmpt in enumerate(self.components):
        cmpt.cmpt_rank = i
    self.cmpt_rank_counter = len(self.components)
```

## Why this is safe

- DOM is not modified — position data lives in an external dict keyed by `id(element)`
- Extraction order is unchanged — `_ads_top()` still runs before `_main_column()` to prevent tads from appearing inside other components
- Only main-section components are reordered by DOM position; header/footer/rhs preserve insertion order
- Missing elements fall back to `float('inf')` (sort last)
- Ancestor detection prevents wrapper elements from always sorting before their children

## Test results

- **70 passed** after snapshot update for `9101d12ab778` ("how to change a tire")
- The snapshot change is a legitimate reorder: ai_overview moves to rank 0 (was rank 1), ad moves to rank 1 (was rank 0) — matches DOM order
- All other 61 fixtures unchanged — ancestor detection preserves extraction order when components share a wrapper element
- One known ad parse error ("no subcomponents parsed") in `9101d12ab778` is pre-existing and unrelated to this change

## Cheap Flights Extraction Failure (resolved)

"cheap flights to new york" only produced 6 results (all ads). Root cause was two issues stacked together.

### 1. `tadsb` inside rso blocked main column extraction

The bottom ads (`div#tadsb`) were nested inside the flights widget in rso. `_ads_bottom()` ran after `_main_column()`, so `tadsb` was still in the DOM when `is_valid()` checked the `ULSxyf` wrapper — it rejected the entire wrapper because it found `tadsb` inside. Fix: move `_ads_bottom()` before `_main_column()` in `ExtractorMain.extract()`.

### 2. Flights tab not recognized by standard-0 layout

The flights SERP uses `kp-wp-tab-AIRFARES` instead of `kp-wp-tab-overview`. The standard-0 layout only checked for `kp-wp-tab-overview`, so the 14 `A6K0A` component divs inside the AIRFARES tab were never extracted. Fix: add `standard-4` layout entry for `kp-wp-tab-AIRFARES`.

### 3. Flights widgets misclassified

The flights price and flight status widgets were classified as `general` (matched `format-04` via a `div.g` deep inside) or fell through to `unknown`. Fix: add `flights` classifier checking for heading text starting with "Flight". Initial attempt used `div.xfX4Ac` but that class is shared with stock/finance widgets (caught by `aapl stock price` fixture `f6fae1c9a96e`).

### Result

20 results extracted (was 6): flights widget, 4 top ads, 9 general results, People Also Ask, flight status, related searches, 2 bottom ads. All 70 tests pass.
