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

### 2026-05-27 — option B executed: full migration to selectolax, ~2x faster

Maintainer green-lit breaking the bs4 contract and asked to push the migration
through to green. Implemented option B via a bs4-compatible adapter
(`WebSearcher/_slx.py`, `SoupNode`) so the ~50 parsers, classifier, and extractor
run unchanged on a selectolax (lexbor) tree; `make_soup` returns the adapter.

**Adapter faithfulness** (to keep `parse_serp` output byte-identical): bs4 class
semantics (single-token / multi-token-exact / list-OR), `name=True` any-tag,
`string=True` via bs4 `.string`, callable filters, `find_parent`, `recursive=False`,
`.div`/`.span` first-descendant access. `get_text` skips script/style/template
text (bs4+lxml does). `extract()` detaches via `remove(recursive=False)`,
preserving the subtree and a stable node identity (`mem_id`) so DOM-position
reordering still resolves — `id()`-keyed ordering switched to `mem_id`.

**Performance.** The first cut matched `find`/`find_all` with a pure-Python
descendant walk → ~451 ms/SERP (slower than bs4). Two fixes captured the win:
1. route translatable `find`/`find_all` through the lexbor CSS engine
   (`node.css()`); exclude self (css matches self, bs4 searches descendants only).
2. `find(string=re.compile)` (has_captcha) scanned every element's full subtree
   text — O(elements × subtree). Scan text nodes directly instead. This was the
   dominant profile cost (~40 s of 54 s).

Clean back-to-back A/B (same idle machine, 60-SERP subset, `.venv313` / Py 3.13):

| Build | Per-SERP median | Corpus/pass |
|---|---|---|
| bs4+lxml (pre-migration `d4ead9e`) | 236.8 ms | 14,636 ms |
| selectolax (this branch) | ~107–116 ms | ~7,175 ms |

**~2.05x faster.** Validated against `_build_css`/native vs Python paths.

**Snapshots:** 10 SERPs updated for benign whitespace-only differences in
concatenated text fields (lexbor emits more whitespace-only text nodes than lxml;
content byte-identical otherwise — verified by whitespace-collapse equality). All
other output unchanged. `get_text` keeps the Python walker: selectolax native
`.text()` changes whitespace in ways that *alter downstream parsing*
(local_results address/directions, a knowledge sub_type) so it is not a safe
substitute. Full suite green: 299 passed, 66 snapshots (Python 3.13).

bs4/lxml are still imported for type annotations and a couple of helpers; fully
removing them is follow-up. selectolax moved to runtime `dependencies`.

### 2026-05-27 — latent fragility exposed by the native-`.text()` experiment

The migration itself is byte-identical (the adapter's `get_text` reproduces bs4
exactly), so none of the below are migration regressions. But the failed
experiment to use selectolax's native `.text()` (whose `strip=True` strips each
fragment yet keeps empties, instead of bs4's strip-then-drop-empties) surfaced
several places where parser correctness leans on **incidental `get_text`
whitespace behavior** rather than enforcing it. These are pre-existing loose
foundations — worth a separate cleanup, independent of the backend.

**1. Slug-style `sub_type` derivation doesn't normalize whitespace (4 sites).**
- `knowledge.py:148` `heading_text.lower().replace(" & ", "-and-").replace(" ", "-")`
- `local_results.py:29` `header_lower.replace(" ", "_")`
- `searches_related.py:28` `header.lower().replace(" ", "_")`
- `perspectives.py:17` `header.text.strip().lower().replace(" ", "_")`

  Each maps a heading to a slug by replacing only the ASCII space. They look
  clean on the corpus *only because* bs4 `get_text(" ", strip=True)` collapses
  ASCII-space runs as a side effect (strip each fragment, drop empties, join with
  a single space). They do **not** handle leading/trailing or doubled spaces
  themselves, and a heading containing a non-breaking/unicode space (`\xa0`, etc.)
  would yield a malformed slug (`co\xa0op`, double `__`) under **bs4 too** — the
  corpus just never exercises it. Native `.text()` made the latent case real
  (`" Cast "` → `-cast-`). Fix: normalize first, e.g. `"-".join(text.split())` /
  `"_".join(text.split())` (a small shared `slugify` helper), which is robust to
  any whitespace and backend-independent.

**2. Link lookup keyed on visible anchor text (`local_results.py:91-99, 74-76`).**
  `_link_text_to_url` builds `key = a.get_text(strip=True).lower()` and
  `parse_local_details` then reads `links_dict["website"]` / `["directions"]` by
  literal English key. This is fragile twice over: (a) it assumes `strip=True`
  yields exactly `"directions"` with no stray whitespace (native `.text()`
  produced `" directions "`, dropping the field), and (b) it is English-only —
  localized SERPs ("Itinéraire", "Sitio web") silently miss `website`/
  `directions`. Prefer a stable structural signal (icon/`data-*`/`aria-label`/
  `jsname`) over visible text for these well-known links.

**3. The `text` field captures incidental whitespace (`local_results.py:52`).**
  `get_text(separator="<|>")` (strip=False) emits empty whitespace text nodes as
  bare `<|> <|> <|>` segments; their count is parser-backend-dependent (this is
  the source of the 10 benign whitespace-only snapshot updates). The stored
  `text` value is noisy regardless of backend. If this field is meant for
  consumption, consider `strip=True` or a normalization pass (a deliberate change
  — it would move snapshots).

**Why this matters beyond tidiness.** `parse_local_details._classify_row` is the
*good* pattern — it classifies each `·`-part by content (regex for rating /
phone / address / hours), so it is whitespace- and order-robust. The fragile
sites instead treat `get_text` output as structured data via positional
`replace`/dict-key. If items 1–2 were made whitespace- and structure-robust, the
parsers would no longer depend on `get_text`'s exact semantics — which in turn
would make selectolax's native C `.text()` a *safe* drop-in, unlocking a further
speedup on top of the ~2x already banked. Recommend a small follow-up: a shared
`slugify(text)` helper for the four `sub_type` sites and a structural rewrite of
the local-results link lookup, each gated on the snapshot suite.

### 2026-05-27 — acted on the fragility notes (slug helper + heading enrichment)

Picked the cleanup up immediately rather than letting it bit-rot, since the
notes pointed at a coherent change. Decisions:

- **Slug helper.** Added `utils.slugify(text, sep)` and routed all four
  `sub_type` derivations (`knowledge`, `local_results`, `searches_related`,
  `perspectives`) through it. `sub_type` is now whitespace-robust (handles
  nbsp/tabs/doubled spaces) and the `-cast-` class of latent bug can't surface
  under either backend.
- **Heading preservation goes in `details["heading"]`, not top-level `title`.**
  `BaseResult.title` is documented as the *result's* title (e.g. the business
  name on a local-results card, the story title on a perspectives card). Reusing
  it for a component-level header would muddy that semantics. `details["heading"]`
  is the established convention -- `knowledge.py` already uses it (3 prior
  sites) -- so the three other parsers now match: `searches_related` and
  `perspectives` and `local_results` each preserve the raw heading there.
- **Local-results link lookup rewritten structurally.** `_link_text_to_url`
  now keys off the stable classes (`a.L48Cpd` for website, `a.VDgVie` for
  directions) instead of the localized visible anchor text. Backend- *and*
  locale-independent, and unaffected by stray-whitespace stripping bugs.

This is a deliberate output enrichment (new `details["heading"]` keys, cleaner
slugs, stable links), not a migration regression -- 63 snapshots regenerated and
the diff verified to contain only `details["heading"]` / `sub_type` / `website` /
`directions` changes. Full suite green (299 passed, 66 snapshots).

**Knock-on benefit toward the native-`.text()` ambition.** With the slug
derivation no longer dependent on `get_text`'s exact whitespace behavior and the
link lookup no longer keying on stripped anchor text, the two parsers that broke
under native `.text()` (`local_results` address/directions and the knowledge
`-cast-`) are now backend-independent. The remaining barrier to using native
selectolax `.text()` for `get_text` is the bs4 `strip=True` drop-empties
semantics in general; the parser-level brittleness side of that wall is now
gone.

### 2026-05-29 — native rewrite complete (adapter removed)

Final pass: ripped out the `SoupNode` adapter and the bs4 + lxml runtime deps.

- **`_slx.py`** went from a 722-line bs4-compatible `Node` wrapper class to a
  ~250-line module of pure functions (`make_soup`, `get_text`, `class_tokens`,
  `walk_descendants`, `subtree_first` / `subtree_css`, `find_text`, `node_string`,
  `next_sibling` / `previous_sibling` / `next_siblings`, `reparse_fragment`,
  `has_text`, `_build_css`). The remaining helpers exist because selectolax's
  native API differs from bs4 in ways that bit downstream parsers: native
  `Node.text(strip=True)` keeps empty fragments; native `node.css()` matches
  self; native `node.traverse()` walks the entire document; native `.next` may
  skip text nodes; native `class` is a string, not a list.
- **Adapter removal** propagated through `utils.py`, `components.py`,
  `classifiers/main.py` + `footer.py`, all four extractors, and
  `extractor_serp_features.py` — every `_unwrap(...)` call and every
  `hasattr(elem, "raw")` shim is gone. Type hints are `Node` end-to-end. The
  `Tag = BeautifulSoup = SoupElement = Node` aliases in `utils.py` stay (one is
  in a function annotation; the others are public surface).
- **Runtime deps** dropped `beautifulsoup4` and `lxml`; both moved to the dev
  group for the six bench/dev scripts that still use them
  (`diff_parsers`, `show_serp`, `dump_ai_overview_html`, `survey_ai_overviews`,
  `inspect_ai_overview_structure`, `demo_screenshot`). Lockfile regenerated.
- **README** swapped "built on `BeautifulSoup`" for "built on `selectolax`".

**Bench (5 iter x 3 runs over 66 SERPs, py3.13, .venv313):**
median 72.6 ms/SERP — vs the 122.4 ms bs4 baseline (`/tmp/bench_baseline_68b8423.txt`)
and ~107-116 ms with the adapter. The remaining headroom over the adapter came
from dropping the per-node Python wrapper class on every traversal/CSS query.

Suite: 299 passed, 66 snapshots, ruff clean.

### 2026-05-29 — head-to-head bench vs. pre-branch baseline

Ran `scripts/bench_parse.py --iterations 50 --runs 5` over the same 5 fixtures
(66 SERPs) on both the branch tip (`94bc682`) and the pre-branch merge-base
(`9e633bf`, dev tip, bs4+lxml), same machine. The pre-branch worktree was so
much slower that runs 3-5 were cut after two near-identical runs established the
baseline (each old run is ~7 min; the two were within 2 ms of each other).

| Metric          | Before (`9e633bf`, bs4+lxml) | This branch (selectolax) | Change       |
|-----------------|------------------------------|--------------------------|--------------|
| Corpus total    | ~6812 ms                     | ~1317 ms                 | ~5.2x faster |
| Median / SERP   | ~98 ms                       | 19.0 ms                  | ~5.2x faster |
| Inter-run spread| 6811.6 / 6813.8 ms (~2 ms)   | MAD 9.1 ms, spread 80.2 ms | both stable |

New-branch per-SERP detail (final run): median 19.031 ms, MAD 4.402 ms, min
6.927 / p90 31.638 / max 43.832 ms; corpus noise floor ~1.4%. The ~5x speedup is
far above that floor.
