# Finding extraction gaps (silently missing results)

A parser can fail two ways: it can *error* (loud, easy to find), or it can *silently
drop* content that is present in the HTML — emitting a clean, plausible result set
that is simply missing components. The second kind hides behind "this SERP just
didn't have many results." This guide is the repeatable method for telling those
apart and turning a real gap into fixtures + a fix.

It was written from the investigation that found WebSearcher dropping the organic
results on `kp-wholepage` (whole-page knowledge panel) SERPs — see the worked
example at the end. Use it whenever you suspect "few / no results found" might
actually be the parser, not Google.

## The signal: separate "legitimately empty" from "suspiciously empty"

Start from parsed output at scale (a parsed corpus, or a downstream parquet of
results) and find SERPs with **zero organic results** (`type == "general"`). Most
will be legitimate — a knowledge answer, a map, a "did you mean". The trick is to
cross-reference each zero-organic SERP against **Google's own signals**, which the
collector records independently of the parser:

| Signal | Source | Reading |
|--------|--------|---------|
| `result_estimate_count` | the "About N results" line | huge for *any* real query — a weak discriminator on its own |
| `notice_no_results` | Google's "did not match any documents" banner | `True` → genuinely empty, drop from suspects |
| `response_code` | HTTP status | `!= 200` → a fetch problem, not an extraction problem |

A SERP is **suspect** when the fetch was clean (`200`), Google did **not** say
"no results", yet the parser emitted **0 organics**. Don't over-trust
`result_estimate_count` (it is billions for "good times cast"); the durable tell is
*"a component class that almost always co-occurs with organics is present, but
organics are not."* In the worked example that co-occurring class was the knowledge
panel: **a SERP with a knowledge panel — especially a right-hand `knowledge_rhs`
panel — and zero organics is structurally odd**, because the panel normally sits
*beside/above* the organic column, not instead of it.

## Confirm the miss against raw HTML

Pull the raw HTML for a handful of suspects and probe for organic-result markers the
parser should have caught. Modern Google organic blocks are `div.g` wrappers each
containing a `div.tF2Cxc` (title/link/snippet); the main column is `div#rso`.

```python
from WebSearcher import utils
from WebSearcher._slx import subtree_css   # selectolax subtree query

soup = utils.make_soup(html)
rso  = soup.css_first('div[id="rso"]')
organics = subtree_css(rso, "div.tF2Cxc")        # organic content blocks
print("organic blocks in HTML:", len(organics))  # >0 here but parser emitted 0 => gap
```

Then **prove they are real** — pull title + external URL from each block — so you are
not chasing a styling class that happens to reuse `tF2Cxc`:

```python
for blk in subtree_css(rso, "div.tF2Cxc")[:5]:
    h3 = blk.css_first("h3"); a = blk.css_first("a")
    print(h3 and h3.text(), "->", a and a.attributes.get("href"))
```

If the URLs point at real sites (Wikipedia, IMDb, news, …) and `parse_serp(html)`
reports `general == 0`, the gap is confirmed.

## Find the structural root cause

Don't guess from class names — **trace the DOM**. Walk the parent chain from one
organic block up to `#rso` and read where it actually lives:

```python
node, chain = organics[0], []
while node is not None and node.attributes.get("id") != "rso":
    chain.append(f"{node.tag}#{node.attributes.get('id')}.{[*node.attributes.get('class','').split()][:2]}")
    node = node.parent
print(" -> ".join(reversed(chain)))
```

The chain tells you *which container the extractor stopped at*. Cross-read it against
the layout handler in `extractors/extractor_main.py`: the standard layout walks the
**direct children of `#rso`**, keeping each attributed child as one component. If the
organics are nested under a single wrapper child, they collapse into that one
component and inherit its (non-`general`) classification.

## Measure the breadth before fixing

A single example can be a one-off; a fix should target a *pattern*. Sample many
suspects, group them by the structural variant the chain revealed, and confirm the
invariant holds across the group. This both sizes the impact and stops you from
overfitting the fix to one tab name:

```python
# group suspects by the kp-wp-tab-* container that holds their organics
from collections import Counter
variants = Counter()
for html in suspect_htmls:
    soup = utils.make_soup(html); rso = soup.css_first('div[id="rso"]')
    for blk in subtree_css(rso, "div.tF2Cxc"):
        n = blk
        while n is not None and n.attributes.get("id") != "rso":
            cid = n.attributes.get("id") or ""
            if cid.startswith("kp-wp-tab"): variants[cid] += 1
            n = n.parent
print(variants.most_common())
```

If the variant *names* are many but the *structure* is one (here: organics always
nested in a `kp-wholepage` tab), the fix must be **structural**, not a per-name
allow-list.

## Capture fixtures, then fix

Pick 3–5 records that span the structural variety (not 5 near-duplicates) and add
them to the corpus per [fixture-corpus.md](fixture-corpus.md), with a `note` that
states the gap explicitly (e.g. "embeds N organic tF2Cxc results … currently
dropped"). Generate baseline snapshots **before** the fix so the post-fix snapshot
diff *is* the proof the gap closed.

## Verify the recovery is additive, correctly typed, and complete

A green snapshot suite does **not** prove the fix is right: snapshots record whatever
the parser emits, so they happily freeze duplicate, over-split, *or mistyped* rows.
When a fix *adds* components, audit it explicitly — a passing suite hid every failure
below until it was checked by hand. Four checks, all cheap:

1. **Don't re-extract what another path already emits (duplicates).** A recovery that
   fires for every layout will double-count on layouts that already handle the
   structure. In the worked example the first attempt ran for all standard variants and
   turned `standard-overview` SERPs from `general 6 → 12` — every result twice — because
   that recipe already decomposes the panel. Compare per-record type counts **against
   the pre-fix snapshot**, not just within the new run; a `general` count that *doubles*
   (rather than rises from 0) is the tell. Fix by scoping the recovery to the path that
   actually drops the data — ideally a **distinct layout label** routed to its own
   extractor, so it can never collide with a path that already works (and the
   distinction shows up in `main_layout`).

   ```python
   live = Counter(c["type"] for c in parse_serp(html)["results"])
   pre  = Counter(c["type"] for c in load_snapshot(serp_id))   # committed = pre-fix
   # a recovery should turn 0 -> N, never N -> ~2N
   ```

2. **Check the added rows aren't duplicates of each other or of siblings.** Per SERP:
   distinct URLs among the recovered components should equal their count, and should
   not intersect the URLs already carried by the knowledge/other components.

   ```python
   gen = [c["url"] for c in results if c["type"] == "general" and c.get("url")]
   assert len(gen) == len(set(gen))                                   # no self-dupes
   assert not (set(gen) & {c["url"] for c in results if c["type"] != "general"})
   ```

3. **Don't over-split structured results.** A single organic with sub-results
   (sitelinks, an image strip, indented subs) must stay **one** component with
   `sub_rank`s/`details`, not become N top-level rows. Confirm the recovered nodes
   aren't nested inside one another (extracting both a wrapper and its child splits one
   result in two) and that `sub_type`/`details`-bearing results survive intact.

4. **Verify each recovered block's *type* against the rendered HTML — not just its
   URL.** This is the check that catches the deepest failure, and the only one a URL
   audit cannot. A recovered block can dedupe perfectly and still be **the wrong
   type**, and a region you assumed was "swallowed organics" can actually be a whole
   **mini-SERP** — organics interleaved with widgets, carousels, and Q&A panels. In the
   worked example, "recovering the organics" from an election panel produced 10 clean,
   distinct `general` URLs that *passed checks 1–3* — yet one was a mislabeled
   election-dates **widget**, and an election-results panel, a `top_stories` block, and
   a resources panel were **missing entirely** (they aren't `div.g`, so a
   `div.g → general` recovery never sees them). Open the actual SERP and walk the
   region top to bottom: does every block you emit match what's rendered there, and is
   every rendered block emitted? If the region is a mini-SERP, stop cherry-picking by
   marker and instead **run the whole sub-column through the normal classify→parse
   pipeline** so each block lands as its true type (and genuinely-new blocks surface as
   `unknown` to become new component types). A marker-based recovery is only safe for a
   region that is *uniformly* the type you assume.

---

## Worked example: organics swallowed by `kp-wholepage` whole-page panels

**Signal.** In a 102k-SERP crawl, 1,479 SERPs had 0 organics. Triage: 101 had
`notice_no_results`, all were `response_code==200`; the rest were knowledge / map /
"did you mean" pages — *except* **1,046 with a knowledge panel and 0 organics**, 625
of those with a right-hand panel. That co-occurrence was the suspect set.

**Confirmation.** Sampling those, every one was a full SERP: e.g. "good times cast",
"footloose cast", "education pronunciation" each carried 8–10 `div.tF2Cxc` organic
blocks (IMDb, Wikipedia, …) under `#rso`, while `parse_serp` returned `general == 0`.

**Root cause.** The parent chain showed the organics nested deep inside a
knowledge-panel tab:

```
#rso → div.ULSxyf (sole child) → div.kp-wholepage → … → div#kp-wp-tab-<X> → div.g.Ww4FFb (organic)
```

`extract_from_standard` → `extract_children(#rso)` grabs the single `div.ULSxyf`
wrapper as **one** component; it classifies as `knowledge`, and the `div.g` organics
nested in its tabs are never emitted as `general`.

**Breadth.** Across 150 sampled suspects there were **37+ distinct `kp-wp-tab`
variants** (`FilmCast`, `ElectionResults`, `Pronunciation`,
`default_tab:kc:/music/recording_cluster:lyrics`, …) and **0** with organics outside
a `kp-wholepage` tab — confirming a single structural invariant under many names, so
a per-name recipe (the existing `_STANDARD_LAYOUTS` entries) is the wrong shape.

**Fixtures.** Five structurally diverse records (music/lyrics, dictionary, film cast,
election, book/author) were added to `tests/fixtures/serps.json.bz2` with baseline
snapshots capturing the dropped state.

## The fix (interim — superseded by [plan 033](../plans/033-kp-wholepage-tab-subcolumn-extraction.md))

> This `div.g → general` recovery is sound only for *uniformly-organic* tabs; check 4
> showed it mislabels/misses content on rich tabs. Kept here as the worked example of
> the iteration; the durable fix is sub-column parsing (plan 033). Read on for the
> reasoning and the wrong turns it cost.

Give the swallowed case its **own layout** rather than force-fitting it into the
generic `standard` extractor. In `extract_from_standard`, after the existing
`_STANDARD_LAYOUTS` sub-recipes are tried and the generic column is built, detect a
`kp-wholepage` with embedded `div.g` organics; if found, label the page
`standard-kp-wholepage` and return the panel column **plus** the recovered organics:

```python
col = ExtractorMain.extract_children(rso_div, drop_tags)   # -> [div.ULSxyf] (the panel)
col = [c for c in (top_divs + col) if ExtractorMain.is_valid(c)]

organics = ExtractorMain._kp_wholepage_organics(rso_div)
if organics:
    self.layout_label = "standard-kp-wholepage"
    return col + organics          # panel -> knowledge, organics -> general
```

```python
@staticmethod
def _kp_wholepage_organics(rso_div: Node) -> list[Node]:
    kp = rso_div.css_first("div.kp-wholepage")
    if kp is None:
        return []
    organics, seen = [], set()
    for tf in subtree_css(kp, "div.tF2Cxc"):
        g = tf
        while g is not None and g.mem_id != kp.mem_id and "g" not in class_tokens(g):
            g = g.parent
        if g is None or g.mem_id == kp.mem_id:   # bare tF2Cxc -> a recipe already emits it
            continue
        if g.mem_id not in seen and has_text(g):
            seen.add(g.mem_id)
            organics.append(g)
    return organics
```

Why a named layout instead of a post-hoc pass, and three details each forced by a
counter-example found while iterating (this is the value of the breadth scan + a
diverse fixture set — every wrong turn was a real SERP):

1. **A distinct layout, detected only in the generic standard branch.** The first
   attempt ran the recovery in `_main_column` for *every* layout. That **duplicated**
   organics on `standard-overview` SERPs ("central park new york" went `general 6 →
   12`, each result twice), because that sub-recipe *already* decomposes the panel
   into knowledge + general. Detecting `standard-kp-wholepage` only where the generic
   path would otherwise emit the panel as one lump avoids the collision, and the new
   label makes the feature visible in `features.main_layout` instead of hiding it.

2. **Bound the parent-climb at the `kp-wholepage` root.** Climbing from a `tF2Cxc` to
   its enclosing `div.g` must stop at the panel; an unbounded climb walks off the top
   of the tree and calls `class_tokens` on a non-element node →
   `TypeError: attrs is only available on element nodes`. Crashed on the first record
   whose organics had no `div.g` wrapper.

3. **Only recover `div.g`-wrapped organics; skip bare `tF2Cxc`.** Airfares/finance
   panels carry bare `tF2Cxc` with no `div.g` wrapper; airfares are already emitted by
   the `standard-airfares` recipe, so re-extracting them produced **duplicate `unknown`
   rows** ("cheap flights" → `general:10 + unknown:10`). Restricting to the classic
   `div.g` wrapper recovers the genuinely-swallowed organics and leaves recipe-handled
   panels alone.

**Result.** The fix changed exactly the 5 swallowed `standard` fixtures, each a pure
`{general: +N}` recovery (7–9 organics) now labeled `standard-kp-wholepage`; recovered
organics are distinct (no duplicate URLs, no overlap with the panel) and carry real
title/url (`test_general_results_have_title_or_url`). The 5 corpus `standard-overview`
SERPs are untouched. Full suite: **331 passed, 4 skipped, 85 snapshots**.

**Interim — this `div.g → general` recovery is unsound for rich tabs (see check 4).**
It is correct only when a tab is *uniformly* organics (e.g. "footloose cast"). Auditing
"az primaries" by type against the rendered HTML (check 4) showed a kp-wholepage tab is
really a **mini-SERP**: the marker-based recovery mislabeled an election-dates widget as
`general` and missed an election-results panel, a `top_stories` block, and a resources
panel entirely. And finance tabs ("aapl") render organics as bare `tF2Cxc` that a recipe
extracts but whose general parser collapses to one result. The sound fix is to stop
cherry-picking and **parse the whole tab as a sub-column** through the normal
classify→parse pipeline, adding component types for the specialized blocks — tracked in
[plan 033](../plans/033-kp-wholepage-tab-subcolumn-extraction.md), which supersedes this
recovery and the `format-06` classifier hack.

