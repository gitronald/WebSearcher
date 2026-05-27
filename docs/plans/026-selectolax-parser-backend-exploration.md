---
status: draft
branch: claude/selectolax-optimization-plan-dDKmP
created: 2026-05-27T07:47:46+00:00
completed:
pr:
---

# Explore replacing bs4/lxml with selectolax in the parse path

A scoping plan, not a commitment to migrate. It maps **where** selectolax
(lexbor) could replace BeautifulSoup+lxml, what each replacement is worth against
the profile we already have, and — more importantly — what makes a naive swap
unsafe. The output of this plan is a go/no-go decision backed by a parity harness
and a measured pilot, not a 50-file rewrite taken on faith.

## 1. Why selectolax, and what 023 already told us

Plan [023](023-parse-pipeline-optimization-revised.md) profiled `parse_serp` over
the fixture corpus and found the cost split (post the `str(soup)` removal):

| Phase | ~% of parse | 023's disposition |
|---|---|---|
| bs4 `find`/`find_all` traversal (classify + parse + extract) | **~60%** combined | The dominant cost. Partly attacked by 3a signal preconditions; the "shared per-component scan" was investigated and **rejected** as too risky for bs4. |
| `make_soup` (lxml parse of a ~1 MB doc) | **~16–18%** | Treated as fixed. `SoupStrainer` judged unsafe (parsers navigate the full tree). |
| `str(soup)` serialization | was ~18.5% | **Already removed** (023 item 5). |

The two biggest remaining levers — lxml parse time and bs4 `find` traversal
volume — are exactly what selectolax targets: lexbor is a C HTML5 parser with C
CSS-selector queries, typically multiple× faster than lxml-parse + bs4-traverse,
at lower memory. 023 explicitly left both on the table as "known but not worth it
**for bs4**." selectolax is the lever that could make them worth it.

So the upside is real and aimed at the measured hot spots. The rest of this plan
is about whether it can be banked **without breaking the byte-identical output
contract** (§2 #1). The BeautifulSoup *input/return-type* contract has been
cleared for breaking (§2 #2), so the migration is a one-way rewrite, not a
dual-backend exercise.

## 2. The binding constraint, and the one we're allowed to break

1. **HARD: `uv run pytest` snapshots must stay green WITHOUT updates.** The
   snapshot suite freezes full `parse_serp` **output** (the result/feature dicts)
   across the `serps-v*` corpus. Any parser that changes one byte of output is a
   regression, not an optimization. This is the gate every change in 023 and 025
   had to clear, and it is the dominant constraint here because **selectolax
   changes the parse tree, the query semantics, and the text extraction all at
   once.** Note this is about output *values*, independent of the input/return
   *types* in #2 below.
2. **RELAXED (maintainer decision, 2026-05-27): the BeautifulSoup public-API
   contract may be broken.** `parse_serp(serp: str | BeautifulSoup)` accepting a
   `BeautifulSoup` object, `make_soup` / `load_soup` returning `BeautifulSoup`,
   the `Extractor` / `ClassifyMain` / `ClassifyFooter` / `FeatureExtractor` bs4
   `Tag` signatures, and the README's "built on `BeautifulSoup`" claim are all
   **fair game to change**. This removes the dual-backend burden: a full migration
   (§6 option B) becomes a clean one-way rewrite rather than a parallel-backends
   maintenance cost. It is a breaking change → ship under a major/minor version
   bump and update the README accordingly. The byte-identical *output* contract
   (#1) still holds regardless.

## 3. Blast radius: the bs4 API surface in the package

Counts across `WebSearcher/` (the thing a migration has to touch):

| bs4 API | Count | Migration note |
|---|---|---|
| `.find(...)` | 246 | The bulk. `find(name, attrs={dict})` has no selectolax equivalent — rewrite to `.css_first(css)`. |
| `.find_all(...)` | 100 | → `.css(css)`. |
| `.select` / `.select_one` (already CSS) | 4 (2 files) | The **only** spots that map 1:1 — `banner.py`, `general.py`. |
| `recursive=False` | 5 | `.css` is always subtree-recursive; direct-children-only needs `>`-combinator/`.iter()` rework. |
| `.extract()` | 9 | Detach-and-return; used as a side effect (e.g. `ads.extract()` then re-add as a component). selectolax detach semantics differ. |
| `.decompose()` | 2 | Maps to selectolax `.decompose()`. |
| `copy.copy(subtree)` | 1 (`notices.py`) | 023 proved this **clones** the subtree and is load-bearing. selectolax nodes are tied to their tree — no equivalent `copy.copy`. |
| `find(..., re.compile(...))` (regex class match) | 3 (`general.py`) | CSS has no regex; needs `[class*=…]` substring + per-call equivalence check. |
| `find(string=re.compile(...))` | 1 (`utils.has_captcha`) | Text-node search; do via `.text()` + regex. |
| `.parent` | 19 | Maps (`node.parent`). |
| `.children` / `.contents` | 18 | `node.iter(include_text=…)`; text-node inclusion differs from bs4. |
| `.next_sibling` / `.previous_sibling` | 4 | `node.next` / `node.prev` — but bs4 yields text nodes between tags; semantics differ. |
| `.descendants` | 1 (`_ComponentSignals`) | `node.traverse()`. |
| `.strings` / `.stripped_strings` | 3 | selectolax text iteration; whitespace/empty handling differs. |
| `NavigableString` | 2 | No direct equivalent; text nodes are a different concept in selectolax. |

This is a large, pervasive surface. The util helpers in `utils.py`
(`get_div`, `get_text`, `get_link`, `get_link_list`, `find_all_divs`,
`find_children`, `find_by_selectors`, `get_text_by_selectors`, `Selector`) are a
partial chokepoint — many parsers route through them — but **246 `.find` +
100 `.find_all` calls are direct on `Tag`s**, so the helpers do not contain the
blast radius on their own.

## 4. Semantic gaps that will silently change output (the real risk)

These are the traps that pass type-checking and break the snapshot suite — or
worse, break it only on SERPs not in the corpus. Each must be audited, not
assumed:

- **Tree shape: lexbor vs lxml.** They are different HTML parsers. Divergences
  show up on real Google markup: optional-tag insertion, foster-parenting of
  table content, whitespace text nodes, and handling of Google's custom elements
  (`g-img`, `promo-throttler`, `g-scrolling-carousel`, `product-viewer-group`,
  `g-inner-card`, `g-accordion`, `g-tray-header`). A different tree → different
  `find`/traversal results → snapshot diffs. **This is the core risk and must be
  measured first (§5), before any rewrite.**
- **Multi-valued class semantics.** bs4 `attrs={"class": ["a", "b"]}` matches an
  element carrying **either** token (OR); a CSS compound `.a.b` requires **both**
  (AND); `.a, .b` is the OR form. The codebase uses `{"class": [...]}` heavily
  (e.g. `knowledge_panel`, `videos`, `general` submenu selectors). Translating
  each to the *matching* CSS is per-call work — getting it backwards silently
  changes which elements match.
- **`.attrs["class"]` is a list in bs4, a string in selectolax.** Pervasive code
  assumes a list: `cmpt.attrs["class"] == ["g"]`, `"g" in cmpt.attrs["class"]`,
  `any(s in [...] for s in cmpt.attrs["class"])`, `_ComponentSignals`'
  `isinstance(cls, list)`. selectolax `.attributes["class"]` is the raw string
  (and valueless attrs are `None`). Every such site needs a `.split()` / rewrite.
- **`.get_text(separator=" ", strip=…)` vs `.text(separator="", strip=False)`.**
  Defaults and whitespace handling differ. `text`/`title`/`cite` field values are
  produced by these calls — a different separator/strip is a direct byte-diff in
  output.
- **Tree mutation.** The extractor `extract()`s ad blocks out of the tree and
  re-adds them as components; `general.py` `decompose()`s menu children before
  re-reading the title; `notices.py` relies on `copy.copy` cloning. selectolax's
  detach/clone model is different and must be re-derived, not transliterated.

## 5. Prerequisite deliverable: a parser-parity harness (no production change)

Mirroring 023's "profile/measure before optimizing" discipline. Before touching
any parser:

1. **Tree-diff harness — DONE (`scripts/diff_parsers.py`, see Log 2026-05-27).**
   Parses every fixture SERP with both `lxml`+bs4 and `selectolax` and reports
   per-SERP structural divergence (element/tag-name counts) plus signal parity for
   the exact class/id/tag/attr targets the classifier and extractor query. Result:
   **zero divergence on every queried signal across 88 SERPs**; the only
   structural diffs are inert (SVG name casing, `<tbody>` insertion). The §4
   tree-shape risk is measured and small.
2. **Bench parity.** Extend `scripts/bench_parse.py` with a selectolax code path
   so deltas are measured the same way (per-SERP median + MAD, gate on the
   ~3% / 2×-MAD noise floor). Record numbers in the Log; never chain deltas across
   sessions (023's hard-won lesson).
3. **Add `selectolax` to deps only when a pilot proves a banked win** — not
   speculatively.

## 6. Strategy options (ranked) — "where can we replace parts"

- **A. Drop-in `make_soup` backend swap — NOT VIABLE.** Unlike `lxml` ↔
  `html.parser` (both yield bs4 trees), selectolax yields a *different node type
  with a different API*. Changing only `make_soup` breaks all 346 `.find`/
  `.find_all` callers. There is no "just change the parser" option; a backend
  swap **is** a query-layer rewrite. State this plainly so it isn't proposed
  later.
- **B. Full migration (the end target).** Reimplement the `utils` helpers on
  selectolax, then rewrite every direct `.find`/`.find_all`/navigation/`.attrs`
  site across the ~50 component parsers + classifier + extractor. With the
  BeautifulSoup contract cleared for breaking (§2 #2) this is a clean one-way
  rewrite — `make_soup`/`load_soup` return selectolax nodes, `parse_serp` takes a
  string (or a selectolax tree), and bs4 is dropped from `dependencies`. Highest
  reward (attacks both the ~16–18% parse cost and the ~60% query cost), highest
  effort, with the byte-identical **output** contract (§2 #1) as the only gate.
- **C. bs4-compatible shim over selectolax.** A wrapper exposing
  `find`/`find_all`/`get_text`/`attrs`/`children` so per-file churn drops. Likely
  a **poor trade**: the Python-level shim reintroduces the per-call interpreter
  overhead that is the whole reason bs4 is slow — it would keep selectolax's parse
  win but erode its query win. Worth prototyping only to measure, not to ship.
- **D. Narrow measured pilot (recommended first step).** Migrate one hot,
  self-contained read-only path end-to-end onto selectolax behind the §5 parity
  harness, measure, then decide B vs C vs stop. Best pilot candidates from 023's
  profile:
  - **`_ComponentSignals`** (`classifiers/main.py`): one `descendants` walk per
    component building sets of class/id/tag names. Pure read, no mutation, on the
    hot classify path (~21%), and a clean `node.traverse()` + `.attributes`
    rewrite. Highest signal-to-risk pilot.
  - **`FeatureExtractor` soup-path probes** (`extractors/extractor_serp_features.py`):
    already small and scoped (post-023 item 5); a contained second pilot.

  Recommendation: **do D first.** It produces a real measured delta and a concrete
  read on the §4 semantic gaps at a fraction of B's risk, and it directly informs
  the go/no-go.

## 7. Open questions for the maintainer (decide before B)

1. **RESOLVED (2026-05-27): breaking the BeautifulSoup contract is approved.** B
   is therefore a clean one-way rewrite (drop bs4, change return/input types under
   a version bump), not a dual-backend burden. See §2 #2.
2. **What is the target — parse latency, memory, or both?** Selectolax helps both;
   the answer changes which path to pilot first.
3. **Appetite for a ~50-file rewrite** vs banking only the pilot's contained win.
   (With #1 resolved, the only remaining reason not to go straight to B is the
   byte-identical-output risk that the pilot exists to de-risk.)

## 8. Success criteria (for whatever scope is chosen)

- Parser-parity harness committed; tree-divergence count on the corpus enumerated
  and explained.
- Any shipped change: snapshots green **without updates**, and a `bench_parse`
  before/after clearing the noise floor, recorded in the Log.
- `selectolax` added to deps only alongside a change that banks a measured win.

## 9. Out of scope

- The Selenium/requests search path (`search_methods/`) — this plan is parse-only.
- `BaseResult` / `SERPFeatures` schema changes (frozen by 023's constraints).
- Re-litigating the items 023 already settled (e.g. `SoupStrainer`), except where
  selectolax changes their risk/reward.

## Log

### 2026-05-27 — scoping pass (this document)

Inventoried the bs4 API surface (§3) and the semantic gaps (§4) against the
current tree, and cross-referenced 023's profile to point the pilot at the
measured hot spots. Key findings driving the plan:

- A `make_soup`-only swap is not viable (option A) — selectolax is a different
  node API, so a backend swap is a 346-callsite query-layer rewrite.
- The byte-identical snapshot contract is the binding constraint; the largest
  unknown is lexbor-vs-lxml **tree-shape** divergence on Google's custom-element
  markup, which is why the parser-parity harness (§5) is the prerequisite
  deliverable before any production change.
- Recommended sequencing: parity harness → narrow pilot on `_ComponentSignals`
  (read-only, hot classify path) → measure → maintainer decision on full
  migration (B) vs stop. No deps added, no parser code changed yet.

### 2026-05-27 — maintainer decision: BeautifulSoup contract may be broken

Open question #1 resolved: we are free to break the BeautifulSoup public-API
contract (drop the `str | BeautifulSoup` input, change `make_soup`/`load_soup`
return types, drop bs4 from `dependencies`, update the README), under a version
bump. This collapses the §6 option set: there is no longer a dual-backend
maintenance argument, so **B (full migration) is the end target** and option C
(bs4-compat shim) is off the table except as a throwaway measurement aid. The
binding constraint is now solely the byte-identical *output* snapshot suite
(§2 #1) — which is exactly what the §5 parity harness and the §6-D pilot exist to
de-risk. Sequencing is unchanged: harness → pilot → measure → commit to B.

### 2026-05-27 — parity harness delivered; tree-shape risk measured as small

Added `scripts/diff_parsers.py` (§5 item 1) and ran it over the full corpus
(88 SERPs, all 7 `serps-*` fixtures). It parses each SERP with both
`BeautifulSoup(html, "lxml")` (mirroring `utils.make_soup`) and selectolax
`HTMLParser`, with no `import WebSearcher` (so it is unaffected by the env issue
below). selectolax `0.4.10` added to the **dev** group only — not runtime
`dependencies` (consistent with §5: ship it only when a pilot banks a win).

**Result — the §4 "core risk" is empirically small on real Google markup:**

- **Signal parity: zero divergence.** For every class/id/tag/attr signal the
  classifier and extractor key on (rso/rcnt/tads/…, `g-*`/`promo-throttler`/…,
  `g`/`ULSxyf`/`MjjYud`/`yuRUbf`/…, `[role=heading]`, `[data-attrid=…]`,
  `[jscontroller=…]`), bs4 and selectolax match the **same number of nodes on all
  88 SERPs**. The query class-token semantics were made provably equivalent
  (`[class~="x"]` == bs4 `class_="x"`), so this is a real tree-agreement result,
  not a selector artifact.
- **Structural diffs (16/88 SERPs) are confined to two inert classes:**
  1. **SVG element-name casing** — `clipPath`/`clippath`,
     `feGaussianBlur`/`fegaussianblur`, `foreignObject`, `linearGradient`,
     `feColorMatrix`, etc. These are net-zero camelCase↔lowercase pairs: lexbor
     keeps the HTML5 SVG foreign-content casing; lxml lowercases. Same elements,
     different case. **No parser queries SVG internals** (grep: none), so inert.
  2. **`<tbody>` auto-insertion** (10 SERPs, ±1 each) — the two parsers differ on
     inserting an implicit `tbody`. The only table-touching path
     (`general.py` submenu: `sub.find("table").find_all("a")`) is recursive, so it
     reaches the **same anchors regardless** — verified on two divergent SERPs
     (`prouve`, `kelly kettle`): `table → a` counts identical (2/2, 5/5).

Conclusion: the byte-identical-output risk from a parser swap is **much smaller
than §4 feared** — on this corpus, lexbor and lxml agree on every node the
pipeline actually looks at. The remaining work to bank the win is the API rewrite
(query/attr/text/mutation translation, §3–§4), not tree-shape reconciliation. The
§6-D `_ComponentSignals` pilot is the next step to get a measured speed delta.

**Environment caveat (blocks the §2 #1 gate here, not the harness):**
`uv run pytest` and `import WebSearcher` currently fail in this container —
Python is `3.14.0rc2` and the pinned `pydantic 2.13.4` raises `AssertionError`
in `eval_type_backport` while building `models/data.py`. This is a pre-existing
deps/runtime mismatch, independent of selectolax. The snapshot-suite gate
(`uv run pytest` green without updates) cannot be exercised until it is resolved
(pin Python to 3.12/3.13 for the env, or bump pydantic to a 3.14-compatible
release). Flagged for the maintainer; the parity harness sidesteps it by not
importing the package.
