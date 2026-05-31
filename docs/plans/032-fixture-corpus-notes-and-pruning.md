---
status: draft
branch: feature/fixture-corpus-notes
created: 2026-05-31T11:32:26-07:00
completed:
pr:
---

# Annotate and prune the bulk SERP fixture corpus

The bulk SERP fixtures carry rich provenance (`qry`, `timestamp`, `version`,
`user_agent`, `serp_id`, ...) but **no `note`** explaining *why each record is in
the corpus* — unlike the curated `serps-v0.7.2-*` fixtures, which each carry a
hand-written note tying the record to the parser path it guards. This plan adds a
`note` to every surviving record and, in the same pass, (a) prunes records that
purely duplicate the structure and unique parts of another SERP, and (b)
**consolidates all fixtures into a single, version-less file** (`serps.json.bz2`),
to shrink the corpus (especially the 15 MB `serps-v0.6.8` file) and make room for a
more diverse example set later.

Version provenance moves entirely into the per-record `version` field (confirmed
present and populated on all 84 records — see Findings). The filename stops carrying
a version: it currently tracks "which WS release curated the fixture in", which
already drifts from the collecting version in the JSON (e.g. `serps-v0.6.8` records
are `version: 0.6.7a0`; `serps-v0.7.2-*` records are `version: 0.3.9`). That drift
is expected and fine — the JSON is the source of truth.

## Background: how the corpus is stored and tested

Fixtures live in `tests/fixtures/*.json.bz2` — bz2-compressed JSON-lines, one SERP
record per line. There are two classes:

- **Curated single-component fixtures** (`serps-v0.7.2-ads/jobs/knowledge-subcards`)
  — already carry a `note`; out of scope here.
- **Bulk fixtures** (this plan): `serps-v0.6.7` (10), `serps-v0.6.8` (52),
  `serps-parser-coverage` (15), `serps-sge-2024` (7) = **84 records,
  112 MB uncompressed**, no notes.

Crucially, the bulk files are consumed by tests in **two different ways**, which
determines what dropping a record costs:

| File | Consumed by | Coupling | Drop cost |
|------|-------------|----------|-----------|
| `serps-v0.6.7`, `serps-v0.6.8` | `tests/test_parse_serp.py` | parametrized by `serp_id[:12]` (snapshot per record) | **cheap** — delete the matching `tests/__snapshots__/test_parse_serp/*.json` |
| `serps-parser-coverage` | `tests/test_parser_coverage.py` | parametrized by **hardcoded `qry`** | expensive — must edit test parametrize lists |
| `serps-sge-2024` | `tests/test_ai_overview_legacy_sge.py` | hardcoded `qry` in `CONTENT_QRYS`/`FAILURE_QRYS` | expensive — must edit test |

Implication: the prunable redundancy lives almost entirely in the **snapshot-only**
`serps-v0.6.7`/`serps-v0.6.8` files. The `parser-coverage` and `sge-2024` files are
already the curated, query-referenced, diverse set — annotate them, don't prune them.

## Methodology: the corpus profiler

`scripts/profile_fixture_corpus.py` (committed with this plan) parses every bulk
record and emits, per record: provenance, `main_layout`, fired feature flags, the
**component signature** (the set of `(type, sub_type)` pairs present), parse-error
strings, and — corpus-wide — which pairs/layouts are rare (1–2 carriers) and which
records' signatures are a strict subset of another record's.

Reproduce:

```bash
# Human-readable report (per-record + corpus frequency + drop candidates)
uv run python scripts/profile_fixture_corpus.py

# Full machine-readable profile
uv run python scripts/profile_fixture_corpus.py --json > corpus_profile.json
```

**Limitation that drives the two-pass rule below:** the signature captures
`type`/`sub_type` coverage but NOT the richness of the `details` payload. Two
`knowledge/panel` records can exercise very different panel-parser branches, and two
`ai_overview/sectioned` records can carry different section shapes (this is exactly
why all 7 `sge-2024` records are kept despite overlapping signatures — their
distinct AI-overview *shapes* are the contribution). A subset signature is a
**screen**, not a verdict.

`scripts/compare_drop_signatures.py` complements the profiler with an **ordered**
view — the components in SERP order as a concatenated string — under three readings
(pair set / distinct-type order / full ordered string). It answers "does a drop
candidate have a unique *ordered* signature?" and prints the final drop list under
the chosen bar. The full methodology (storage, provenance, signature readings, drop
policy, tooling) lives in [docs/guides/fixture-corpus.md](../guides/fixture-corpus.md).

## Findings

### Version provenance is fully in the JSON (consolidation is safe)

Every record in all seven files carries a non-empty `version` field (verified:
`has_version == n`, zero missing keys, zero empties). So collapsing the seven
version-named files into one `serps.json.bz2` loses no provenance — the collecting
version is per-record. Witnessed values: `parser-coverage` → `0.3.9`, `sge-2024` →
`0.5.0`, `v0.6.7`/`v0.6.8` → `0.6.7a0`, `v0.7.2-*` → `0.3.9`.

### Unique contributors (definite keepers)

Records that are the **sole** carrier of a `(type, sub_type)` pair or layout — these
anchor parser coverage and must never be dropped:

| serp_id | file | qry | unique contribution |
|---------|------|-----|---------------------|
| `2cb96b64e45d` | parser-coverage | drawing tablet | `buying_guide`, `most_read_articles` |
| `760310a7eec2` | parser-coverage | men's old school wears | `products/brands` |
| `880beebb66bb` | parser-coverage | kaka boots | `images/small` |
| `7d621e868493` | parser-coverage | oscar the grouch | `knowledge/played-by`, `knowledge/songs` |
| `eef22ed8a7ee` | parser-coverage | pitbull ... world anthem | `knowledge/lyrics`, `knowledge_rhs` (+ error regression) |
| `2464d0d52a14` | parser-coverage | movement | `local_results/None` |
| `363db5067378` | sge-2024 | honeywell c level ... | `knowledge/featured_snippet` |
| `7b89c00120e3` | v0.6.8 | apple inc | `local_results/locations` |
| `2c0aa0bbcd0c` | v0.6.8 | yoga for beginners | `local_results/businesses` |
| `01f85d1329ba` | v0.6.8 | northern lights | `local_results/places` |
| `9101d12ab778` | v0.6.8 | how to change a tire | `ad/local_service` |
| `5898b04fb534` | v0.6.8 | hotels in manhattan | `locations/hotels`, `shopping_ads/hotels` |
| `7ad9715f3597` | v0.6.8 | 100 fahrenheit to celsius | `knowledge/unit_converter` |
| `56f2eab63e9d` | v0.6.8 | weather today | `knowledge/weather` |
| `b15c5131b06c` | v0.6.8 | nba scores | `knowledge/sports` |
| `d920789249af` | v0.6.8 | cngress usa | `knowledge/things_to_know`, `notice/unknown` |
| `6e401e618433` | v0.6.8 | cheap flights to new york | `flights` + **sole `standard-airfares` layout** |

### Redundancy clusters (prune targets, snapshot-only files)

1. **`serps-v0.6.7` is almost entirely duplicative.** 7 of 10 records are the
   query *"why is the sky blue?"* (`aa594f199c3d`, `6aa70651b0cd`, `97404b7b7c61`,
   `7049404a2dd6`, `45b6e019bfa2`, `c9ab650f5bda`, `032572e185d3`) — all
   `ai_overview/flat + general + perspectives + videos` — plus 2× *"donald trump"*
   and 1× *"why are bananas yellow"*. **Every signature in this file is covered by a
   `serps-v0.6.8` record** (e.g. the sky-blue structure is duplicated by v0.6.8's
   `be99c971b8f7`; `recent_posts` survives in `811a27f92284` "taylor swift";
   `knowledge/featured_results` is common). Recommendation: **keep 2 sky-blue
   records** as representatives of the `ai_overview/flat + perspectives + videos`
   family — `aa594f199c3d` and `6aa70651b0cd` (the two fullest, both carrying the
   extra `images/medium` + `videos/vertical`) — and drop the other 8 v0.6.7 records
   (the 5 thinner sky-blue dupes, "why are bananas yellow", and both "donald trump",
   whose `recent_posts`/`knowledge` structure survives in v0.6.8's `811a27f92284`).
   That trims ~8 records / ~13 MB uncompressed from this query family while keeping a
   couple of intact examples. (Subject to the details second-pass.)

2. **`serps-v0.6.8` pure subsets.** ~20 records whose signature is a strict subset
   of another v0.6.8 keeper (`811a27f92284` taylor swift, `da9b4fce9ab0` best credit
   cards, `dc5861b33dda` coral reef, etc.) and which carry no rare pair:
   `b2e1777bf0f2` (einstein), `f6fae1c9a96e` (aapl), `984065877aad` (is college
   worth it), `e828d00dc1b3` (car insurance), `d1855fa9cd1c` (best mattress forum),
   `d1ac0c4abb10` (medical advice covid), `a6c8fe7fe769` (population of france),
   `3f5efb1dc358` (what causes earthquakes), `be99c971b8f7` (why is the sky blue),
   `8e820f7b024f` (translate good morning), `0d3fc3b49b76`, `2d1b05a046b2`,
   `83b17a6a7750`, `8f98fa9c0bef`, `82e35954f552`, `4c8d8d2f226c`, `a6c881e003e2`,
   and the streaming pair `9ed1baa7715d`/`cad43c3268a8` (identical signatures — keep
   one), and the two paragraph-length covid queries `f006c9318116`/`3c09a0f0c92f`
   (keep one as a pathological-query example).

The unordered pair-set screen flags ~25–30 of these as subsets, but that lens
over-drops (it ignores ordering). The actual drop list is set by the decided
**distinct-type-order bar** (see Plan §3): **8 records**, dominated by 5 redundant
sky-blue captures. The footprint win is modest but real — those 8 (mostly ~1.7 MB
sky-blue HTML) total ~10 MB uncompressed — and the corpus keeps every distinct
component *sequence*.

### CRITICAL mechanical constraint — `standard-overview` layout

`tests/test_parse_serp.py::test_features_expose_main_layout` asserts that
`{"standard", "standard-overview", "standard-airfares"}` all appear across the
**`serps-v*` snapshot set** (that test loads only `serps-v*` via
`load_all_serps()`). Within that set:

- `standard-airfares` → only `6e401e618433` (keeper).
- **`standard-overview` → only `f6fae1c9a96e` ("aapl stock price")**, which is
  otherwise a structural subset of taylor swift.

The `parser-coverage` overview records (oscar/mater/pitbull) are **not** in the
`serps-v*` glob, so they don't satisfy this assertion. Therefore `f6fae1c9a96e`
**must be kept** (or the test must be repointed / an overview record relocated into
a `serps-v*` file) even though the signature screen flags it. The implementation
must re-run this test after any drop.

## Plan

### 1. Note schema

Mirror the existing curated format (one prose string in a `note` field):

```
<provenance clause>. <what is structurally notable + what parser path it guards>.
```

- **Provenance clause** — where/when captured, scrubbed of private detail (see §4).
  e.g. `"Bulk corpus capture, v0.6.7a0 selenium crawl 2026-02-06."`
- **Contribution clause** — for keepers, name the unique pair/layout it anchors
  (e.g. `"Sole carrier of knowledge/unit_converter."`); for retained
  representatives, say what family it represents (e.g. `"Representative
  ai_overview/flat + perspectives + videos SERP."`).

### 2. Add notes to all survivors

Write the `note` field into every surviving record across all four bulk files.
Drive it from `profile_fixture_corpus.py --json`: unique/rare pairs and sole-layout
flags map directly to the contribution clause. Re-compress each file in place
(JSON-lines + bz2), preserving field order where practical.

### 3. Prune

**Drop bar (decided): distinct-type-order signature.** A record may be dropped only
if its distinct-type ordered signature (components in SERP order, repeats collapsed)
is still carried by a surviving record. `general` count/ordering is treated as crawl
noise and does not protect a record; any record with an unseen distinct component
*sequence* is protected. Rationale: the unordered pair-set screen over-drops, and the
full-ordered-string lens never drops (organic `general` counts make ~20/25 candidates
"unique"); distinct-type order is the faithful middle ground.

Applying the bar (`scripts/compare_drop_signatures.py`) yields **8 drops / 17 of the
25 set-subset candidates protected**:

| Drop | qry | distinct-type sig preserved by |
|------|-----|--------------------------------|
| `97404b7b7c61` | why is the sky blue? | `7049404a2dd6` |
| `45b6e019bfa2` | why is the sky blue? | `7049404a2dd6` |
| `c9ab650f5bda` | why is the sky blue? | `7049404a2dd6` |
| `032572e185d3` | why is the sky blue? | `7049404a2dd6` |
| `be99c971b8f7` | why is the sky blue | `7049404a2dd6` |
| `cad43c3268a8` | stream stranger things | `9ed1baa7715d` (watch the office) |
| `3c09a0f0c92f` | medical advice ... (paragraph #2) | `f006c9318116` |
| `984065877aad` | is college worth it | `9a7e39d95bf0` (how does photosynthesis work) |

This keeps **3 sky-blue records** (the 2 rich reps `aa594f199c3d`/`6aa70651b0cd` +
the thin-shape representative `7049404a2dd6`), one of each near-duplicate pair
(streaming, paragraph-query), and every record with a unique distinct-type sequence.

- **Details confirmation (required before deletion):** for each of the 8, diff its
  parsed `results` (including `details`) against its preserving record; only delete
  if `details` adds no parser branch the survivor lacks. Use `scripts/reparse_demo.py`
  / `scripts/show_parsed.py`.
- Apply drops: remove the 8 records from the consolidated file and **delete the
  matching `tests/__snapshots__/test_parse_serp/test_parse_serp[<serp_id[:12]>].json`**.
  Keep `f6fae1c9a96e` regardless (sole snapshot-set `standard-overview`).

### 4. Provenance scrub (fold in while rewriting)

These records are committed to a **public** repo. While rewriting the files:

- Drop the private-repo name from any note text (the curated v0.7.2 notes currently
  say "Captured via SearchAudits ...") — use a neutral provenance clause.
- Scrub the `GOOGLE_ABUSE_EXEMPTION` token + embedded IP from the `url` of
  `serps-v0.6.7` record `7049404a2dd6` (mooted if that file is retired).

### 5. Consolidate into `serps.json.bz2` and update loaders

Merge all survivors (curated v0.7.2 + parser-coverage + sge-2024 + v0.6.7 sky-blue
keepers + v0.6.8 survivors) into a single `tests/fixtures/serps.json.bz2`, then
delete the seven old version-named files. Update the three loaders:

- `tests/test_parse_serp.py` — replace `SERPS_PATHS = glob("serps-v*.json.bz2")`
  with the single file. **Scope decision:** the current glob excludes
  `parser-coverage` and `sge-2024` from the snapshot test; loading one combined file
  means `test_parse_serp` now snapshots **every** record (gains ~22 snapshots for the
  formerly snapshot-excluded records). Recommended: accept the wider coverage and
  generate the new snapshots (`--snapshot-update` once, then review the diff). If we
  want to preserve the old scope instead, filter by a record field — but wider
  coverage is the better default.
- `tests/test_parser_coverage.py` and `tests/test_ai_overview_legacy_sge.py` — both
  already build `{qry: rec}` dicts, so just point `FIXTURE` at `serps.json.bz2`; the
  `qry`-keyed lookups keep working unchanged.
- `scripts/profile_fixture_corpus.py` — replace the `BULK_GLOBS` list with the single
  file (drop the per-file split; keep the same per-record analysis).

### 6. Verify

```bash
uv run pytest tests/test_parse_serp.py tests/test_parser_coverage.py \
  tests/test_ai_overview_legacy_sge.py tests/test_extractor_serp_features.py -q
uv run python scripts/profile_fixture_corpus.py   # confirm no unique pair lost
```

Confirm: no snapshot orphaned or missing; `test_features_expose_main_layout` still
green; corpus-wide `(type, sub_type)` frequency table retains every pair that had a
single carrier.

## Implementation order

1. Commit `scripts/profile_fixture_corpus.py` (the methodology artifact).
2. Pass B details-confirmation on the v0.6.8 candidates; finalize the drop list
   (the 2 v0.6.7 sky-blue keepers are already decided).
3. Build `serps.json.bz2`: collect all survivors, add the `note` field to each,
   scrub provenance (§4), write the combined bz2 JSON-lines file. Delete the seven
   old version-named files.
4. Update the three test loaders + the profiler to point at the single file (§5).
5. Delete orphaned snapshot JSONs for dropped records; `--snapshot-update` to add
   snapshots for the newly-included parser-coverage/sge records, then review the diff
   (should be additions + deletions only, no content changes to surviving records).
6. Run the verify suite (§6); confirm `test_features_expose_main_layout` is green and
   no single-carrier `(type, sub_type)` pair was lost.

## Open questions

- **Consolidated filename:** `serps.json.bz2` proposed. Alternative: `serps-corpus`
  / `serp-fixtures`. Recommended: `serps.json.bz2`.
- **Snapshot scope after consolidation:** widen `test_parse_serp` to snapshot the
  formerly-excluded parser-coverage/sge records (recommended), or preserve current
  scope via a filter field? Recommended: widen.
- **Note storage:** inline `note` field (consistent with v0.7.2) vs. a sidecar
  manifest keyed by `serp_id`. Recommended: inline, for parity.

Resolved: keep 2 v0.6.7 sky-blue records (`aa594f199c3d`, `6aa70651b0cd`) rather
than retiring the file wholesale; consolidate into one version-less file.
- **Should the freed budget be backfilled now** with new diverse captures, or left
  for a follow-up plan? Recommended: follow-up — keep this plan scoped to
  annotate + prune.
