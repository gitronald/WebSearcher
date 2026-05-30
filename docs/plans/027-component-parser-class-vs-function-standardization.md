---
status: draft
branch: claude/component-parser-standardization-3w9XS
created: 2026-05-30T00:00:00-07:00
completed:
pr:
---

# Component Parser Standardization: Class vs. Function

## Goal

The 39 parser modules in `WebSearcher/component_parsers/` mix two
implementation styles: most are plain module-level functions, but two are
built around classes. This plan maps every parser, determines which style is
more efficient and maintainable, and lays out a phased standardization.

---

## Current Map

### Dispatch contract (how parsers are actually called)

`Component.run_parser` (`WebSearcher/components.py:82`) is the single call
site for every registered parser:

```python
if parser_func in {parse_unknown, parse_not_implemented}:
    parsed_list = parser_func(self)        # gets the Component
else:
    parsed_list = parser_func(self.elem)   # gets a selectolax Node
```

**Key fact:** every registered entry parser is handed `self.elem` — a
selectolax `LexborNode`, *not* the `Component`. So the conventional first
parameter name `cmpt` (used in 37 of 39 files) is a misnomer: the value is
always the element node. `footer.py` already names it correctly (`elem`).

The registry (`component_parsers/__init__.py` → `PARSERS`) maps a type-name
string to a callable. Today that callable is one of three shapes:

- a bare module function (`parse_ads`, `parse_general_results`, …) — 36 types
- a **class static method** (`Footer.parse_discover_more`,
  `Footer.parse_image_cards`, `Footer.parse_omitted_notice`) — 3 types
- a **function that wraps a class** (`parse_notices` → `NoticeParser()`) — 1 type

### Style breakdown

| Style | Count | Files |
|-------|-------|-------|
| Module-level function(s) | 37 | everything except the two below |
| Class — static-method namespace | 1 | `footer.py` (`Footer`) |
| Class — per-call stateful instance | 1 | `notices.py` (`NoticeParser`) |

### The two class-based parsers

**`footer.py` — `Footer`** (`component_parsers/footer.py:12`)
- Four `@staticmethod`s: `parse_image_cards`, `parse_image_card`,
  `parse_discover_more`, `parse_omitted_notice`.
- No `__init__`, no instance state, never instantiated. It is purely a
  namespace; the methods are functions with a `Footer.` prefix.
- First param is `elem` (correct).

**`notices.py` — `NoticeParser`** (`component_parsers/notices.py:21`)
- Instantiated fresh on every call through the `parse_notices(cmpt)` wrapper.
- `__init__` rebuilds two dicts every call: `sub_type_text` (6 keys) and
  `parser_dict` (6 bound-method entries).
- Carries mutable scratch state (`self.parsed`, `self.sub_type`,
  `self.parsed_list`) that lives only for the duration of one parse.
- Methods (`_classify_sub_type`, `_parse_sub_type`, `_package_parsed`, and six
  `_parse_*` sub-type handlers) are instance methods only because they read
  that scratch state — none of it needs to persist.

### The dominant function pattern (the de-facto standard)

The 37 function-based modules already share a consistent shape:

```python
def parse_<type>(cmpt, sub_rank: int = 0) -> list:   # entry, gets a Node
    ...
    return [parse_<type>_item(sub, i) for i, sub in enumerate(subs)]

def parse_<type>_item(sub: Node, sub_rank: int = 0) -> dict:
    ...
```

Sub-type routing is done with module functions (`classify_ad_type` in
`ads.py`, `find_subcomponents` in `general.py`, format detection in
`images.py`/`videos.py`/`top_stories.py`) and module-level lookup — no
classes required.

---

## Determination: functions are more efficient *and* more maintainable

### Efficiency

- **Functions:** one call, no allocation; module-level constants are built
  once at import.
- **`Footer` static methods:** behaviourally identical to functions plus one
  extra attribute lookup on `Footer`. Negligible, but also zero benefit.
- **`NoticeParser`:** strictly more work than the alternatives — it allocates
  an object and **rebuilds the `sub_type_text` and `parser_dict` dicts on
  every component parsed**. Those dicts are constant; they belong at module
  scope, built once. This is the only style with measurable per-call overhead.

Verdict: functions (with module-level constants) win; `Footer` ties; the
`NoticeParser` instance pattern is the slowest.

### Maintainability

- **Consistency:** 37/39 modules are already functions. Two outliers force
  contributors to learn three registry-reference styles
  (`fn` vs `Class.method` vs `fn-wrapping-Class`) and two first-param
  conventions (`cmpt` vs `elem`).
- **No encapsulation earned:** neither class uses inheritance, polymorphism,
  or persistent state. `Footer` is namespacing; `NoticeParser` is transient
  scratch state that maps cleanly onto local variables and function args.
- **Discoverability:** `grep "def parse_<type>"` locates a function parser
  immediately; class methods are nested and the notices entry point is a
  thin wrapper indirecting to a class.
- **Testing:** functions and module constants are trivially importable and
  callable in isolation; the stateful class requires constructing an instance.

Verdict: functions are clearly more maintainable here. Classes would only earn
their keep if a parser needed shared state across calls or a real type
hierarchy — neither exists in this codebase.

**Conclusion: standardize on module-level functions + module-level
constants. Retire both classes — but keep `footer.py`'s grouping (see below).**

### Why `footer.py` groups several parsers — and why that stays

`footer.py` is the only parser module exposing more than one registered type
(`discover_more`, `img_cards`, `omitted_notice`). Before changing it, two
things were established:

1. **The class is a vestige, not a design.** Git history shows `Footer` began
   as a `@classmethod` group (`b7cc700` later converted it to
   `@staticmethod`). Its only purpose was letting `parse_image_cards` call its
   sibling `parse_image_card` via `self.` — a pre-namespacing idiom. It has
   never held state. A module gives sibling access for free, so the `class`
   keyword earns nothing.

2. **The *grouping* is deliberate and load-bearing.** "Footer" is a cohesive
   section unit across four layers:

   | Layer | Footer construct |
   |-------|------------------|
   | Registry (`component_types.py`) | `# ----- Footer section -----` block — the only 3 types with `sections=("footer",)` |
   | Extractor (`extractor_footer.py`) | `ExtractorFooter` |
   | Classifier (`classifiers/footer.py`) | `ClassifyFooter` (falls back to `ClassifyMain` for shared types) |
   | Parser (`footer.py`) | the footer-exclusive parsers |

   Types that appear in the footer but aren't footer-exclusive (`general`,
   `searches_related`, `sections=("main","footer")`) are intentionally parsed
   by their **main** parsers — which is why `ClassifyFooter` defers to
   `ClassifyMain.classify`. So `footer.py` owns exactly the footer-native
   types, mirroring `ClassifyFooter` / `ExtractorFooter`.

Therefore: **drop the `class`, keep the module.** Splitting the three parsers
into separate one-type-per-file modules would make the parser layer the only
place that doesn't treat footer as a unit, breaking a symmetry the extractor,
classifier, and registry all rely on. The lone wart is the `class` keyword.

(Caveat for the record: this leaves one section-grouped parser module among 36
type-grouped ones. The fully uniform alternative — section-grouping *all*
parsers to match the classifier layer — is a much larger change and is **not**
proposed here. We accept `footer.py` as a deliberate section module.)

---

## Standardization Plan

### Phase 0 — Establish the contract *and* apply it

Declaring the contract and making the code conform to it are the same step:
the contract says the first parameter is `elem`, so this phase both writes it
down and renames the misnamed `cmpt` parameters. Doing this first means the
Phase 1/2 class conversions are written against an already-true contract.

**0a. Write the contract.** Add a short "Parser contract" section to
`component_parsers/__init__.py`'s module docstring (or a `CONTRIBUTING` note):

- Entry parser signature: `def parse_<type>(elem: Node, sub_rank: int = 0) -> list[dict]`
- First parameter is **`elem`** (a selectolax `LexborNode`), never `cmpt`.
- Returns `list[dict]`; each dict has at least `type` and `sub_rank`.
- Per-item helper: `def parse_<type>_item(sub: Node, sub_rank: int = 0) -> dict`.
- Constants (selector tables, sub-type text maps) live at module scope in
  `UPPER_SNAKE_CASE`, built once at import.

**0b. Apply it — rename `cmpt` → `elem`.** Mechanically rename the entry-parser
first parameter from `cmpt` to `elem` across the ~37 affected files so the name
matches reality (it is always a Node). The positional call site
(`parser_func(self.elem)`) is unaffected. Leave genuine `cmpt: Node` *helper*
params that take sub-nodes alone — only the entry parser's first arg is
misnamed. `footer.py` already uses `elem`, so it's exempt from the rename.

Land 0a and 0b as two commits (doc, then mechanical sweep) for a clean,
reviewable diff.

### Phase 1 — `Footer` class → functions, `footer.py` stays a section module (low risk)

`footer.py` remains the home for all three footer-exclusive parsers (it is a
deliberate section module — see "Why `footer.py` groups several parsers"
above). We remove only the `class` wrapper.

1. In `footer.py`, drop `class Footer:` and dedent the four methods into
   module functions. Realign the names to the registry keys while doing so:
   `parse_image_cards` → `parse_img_cards`, `parse_image_card` →
   `parse_img_card` (the type is `img_cards`, not `image_cards`). Keep
   `parse_discover_more` and `parse_omitted_notice`. Sibling calls become
   direct (`parse_img_cards` → `parse_img_card`), no `self.`/`Footer.`.
2. In `component_parsers/__init__.py`: `from .footer import parse_discover_more,
   parse_img_cards, parse_omitted_notice` and change the three `PARSERS`
   entries (`discover_more`, `img_cards`, `omitted_notice`) from
   `Footer.parse_*` to the bare functions.
3. Update any references to `Footer` in tests/scripts (grep `Footer`).

Behaviour is byte-for-byte identical (pure move + rename); the section grouping
is preserved.

### Phase 2 — Convert `NoticeParser` → functions (medium risk)

1. Hoist the two dicts to module constants: `_SUB_TYPE_TEXT` and a
   `_SUB_TYPE_PARSERS` map built from module-level `_parse_*` functions
   (built once at import, not per call).
2. Rewrite the six `_parse_*` instance methods as module functions taking
   `node: Node` and returning a `dict` (they already only read the node).
3. Make `_classify_sub_type(node) -> str` and `_package_parsed(sub_type,
   parsed) -> list` plain functions.
4. `parse_notices(elem)` becomes: classify → dispatch → package, with no class
   and no per-call dict construction.

Covered by existing notices tests (`tests/test_component_types.py` and any
notice fixtures) — behaviour must stay identical.

### Out of scope: `parse_alink` reconciliation + knowledge rethink

This audit surfaced that `parse_alink` is defined four times (`general.py`,
`knowledge.py`, `knowledge_rhs.py`, `top_image_carousel.py`) with three subtly
different behaviors — not hard duplicates. Reconciling them touches the
knowledge parsers specifically, which we want to rethink more broadly. That
work is **deferred to its own plan** (see
`028-knowledge-parsers-and-alink-reconciliation.md`) and is explicitly **not**
part of the class→function standardization here.

### Validation

After each phase:

```
pytest tests/test_component_types.py tests/test_parser_coverage.py \
       tests/test_ads.py tests/test_ai_overview_payloads.py
pytest                       # full suite
python scripts/diff_parsers.py   # optional: confirm parsed output unchanged
```

Each phase is independently shippable and test-covered, so they can land as
separate commits/PRs.

---

## File Change Summary

| File | Phase | Change |
|------|-------|--------|
| `component_parsers/__init__.py` | 0a,1 | Add contract docstring; import Footer fns; update 3 PARSERS entries |
| `component_parsers/*.py` (~37) | 0b | Rename entry param `cmpt` → `elem` |
| `component_parsers/footer.py` | 1 | Remove `Footer` class (keep module); methods → functions; `parse_image_card(s)` → `parse_img_card(s)` |
| `component_parsers/notices.py` | 2 | Remove `NoticeParser`; methods → functions; dicts → module constants |
## Open Questions

None blocking. `parse_alink` reconciliation and the broader knowledge rethink
are tracked in `028-knowledge-parsers-and-alink-reconciliation.md`.
