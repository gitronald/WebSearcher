# The SERP fixture corpus: provenance, signatures, and pruning

WebSearcher's parser tests run against a corpus of real Google SERPs stored under
`tests/fixtures/`. This guide explains how the corpus is stored, what provenance it
carries, how we measure each record's contribution with a **SERP signature**, and
the policy for deciding when a record is redundant enough to drop. The pruning and
consolidation work is tracked in plan
[032](../plans/032-fixture-corpus-notes-and-pruning.md).

## Storage and format

- **Location:** `tests/fixtures/*.json.bz2`
- **Format:** bz2-compressed **JSON-lines** — one SERP record (a JSON object) per
  line. Load with `bz2.open(path, "rt")` + `orjson.loads` per line.
- A record's raw HTML is in the `html` field; everything else is provenance.

### Provenance fields

Every record carries collection metadata (verified present and populated on all
records):

| Field | Meaning |
|-------|---------|
| `qry` | the search query |
| `url` | the Google search URL requested |
| `timestamp` | ISO collection time |
| `version` | the WebSearcher version that collected the SERP |
| `method` | collection method (`selenium`, etc.) |
| `user_agent` | full UA string |
| `response_code` | HTTP status |
| `serp_id` | content hash; tests key snapshots on `serp_id[:12]` |
| `crawl_id` | crawl batch id (may be empty) |
| `loc`, `lang` | location / language (often empty) |
| `note` | *(curated records)* why this record is in the corpus / what it guards |

`version` is the source of truth for the collecting release. It is **independent of
any version in a filename** — filename versions track "which WS release curated the
record in" and drift from `version` by design (e.g. records collected at `0.3.9`
added during the `0.7.2` line). The consolidation in plan 032 drops version-named
files in favor of a single `serps.json.bz2`, because the JSON already holds the
authoritative version.

## How tests consume the corpus

Two consumption patterns, which determine the cost of dropping a record:

| Consumer | Coupling | Drop cost |
|----------|----------|-----------|
| `tests/test_parse_serp.py` | parametrized by `serp_id[:12]`; one syrupy snapshot per record | cheap — delete the matching `tests/__snapshots__/test_parse_serp/test_parse_serp[<id>].json` |
| `tests/test_parser_coverage.py`, `tests/test_ai_overview_legacy_sge.py` | parametrized by **hardcoded `qry`**; build `{qry: record}` | expensive — must edit the test's query lists |

So redundancy is cheap to prune only in the snapshot-keyed files. The query-keyed
files are the curated, intentionally-diverse set — annotate them, don't prune them.

One coupling to respect: `test_parse_serp.py::test_features_expose_main_layout`
asserts `{"standard", "standard-overview", "standard-airfares"}` all appear across
the snapshot set. Within that set those layouts can have a **single carrier each**
(e.g. one `standard-overview`, one `standard-airfares`), so those records are
protected regardless of signature.

## The SERP signature

A **signature** summarizes a SERP's parsed structure so records can be compared. The
component list is taken in SERP order, one entry per `cmpt_rank` (from its
`sub_rank == 0` row). There are three readings, from loosest to strictest:

1. **Pair set** — the unordered set of `(type, sub_type)` pairs. Ignores order and
   count. Used to find which records are the *sole* carrier of a component type.
2. **Distinct-type order** — the sequence of **distinct** component types in
   first-appearance order, repeats collapsed:
   `ai_overview > people_also_ask > general > perspectives > searches_related`.
3. **Full ordered string** — every component in order including repeats, optionally
   with sub_type: `ai_overview[flat] > people_also_ask > general > general > …`.

The choice of reading matters: ordinary organic results all parse as `general`, so
two SERPs of the same *kind* routinely differ in how many `general` blocks Google
returned and where they sit. Reading 3 calls those unique; readings 1–2 do not. A
unique *string* is not the same as unique *parser coverage*.

## Pruning policy

A record is a **definite keep** if either:

- it is the **sole carrier** of any `(type, sub_type)` pair (pair-set reading), or
- it is the sole carrier of a `main_layout` required by `test_features_expose_main_layout`.

Among the rest, the **drop bar is the distinct-type-order signature** (reading 2): a
record may be dropped only if its distinct-type signature is **still carried by a
surviving record**. Concretely:

- records with a unique distinct-type signature are protected;
- within a cluster sharing a distinct-type signature, keep one representative (the
  fullest by component count) and drop the others;
- a candidate is droppable when a *non-candidate* (a keeper) already carries its
  distinct-type signature.

This deliberately treats `general` count and ordering as crawl noise — it does not
protect a record — while protecting any record whose distinct component *sequence*
is unseen elsewhere. It is the conservative middle ground between the pair-set lens
(which over-drops) and the full-ordered-string lens (which never drops).

## Tooling

Three scripts, all run through `uv`. They are **report-only** — none mutates the
corpus or auto-recommends deletions (the plan-032 drop decision is already applied;
`scripts/build_fixture_corpus.py` is the one-time builder that produced the file).

### `scripts/profile_fixture_corpus.py`

Parses every record and reports per-record provenance, `main_layout`, fired feature
flags, the pair-set signature, parse errors, and corpus-wide rarity (which pairs /
layouts have only 1–2 carriers).

```bash
uv run python scripts/profile_fixture_corpus.py            # human-readable report
uv run python scripts/profile_fixture_corpus.py --json     # machine-readable
```

### `scripts/compare_drop_signatures.py`

Reports the three signature readings and surfaces **distinct-type signature
clusters** (records sharing a component sequence) for human review.

It does NOT recommend drops, by design. A shared `(type, sub_type)` signature is
blind to details-level structure: e.g. two `ai_overview/sectioned` records can
differ in section *count* (1 vs 3), and `test_ai_overview_legacy_sge.py` depends on
the multi-section one specifically. Always confirm at the details level — and check
the query-keyed tests — before treating a cluster as redundant.

```bash
uv run python scripts/compare_drop_signatures.py
```

### `scripts/verify_drops.py`

Corpus-integrity guard: confirms the 8 plan-032 drops are absent, serp_ids are
unique, every record carries a `note`, the three witnessed layouts survive, and
every parsed `(type, sub_type)` has a carrier. Exits non-zero on failure (CI-usable).

```bash
uv run python scripts/verify_drops.py
```

## The `note` field

Surviving records should carry a `note` mirroring the curated format — a provenance
clause plus what the record contributes:

```
<provenance>. <structurally notable feature + the parser path it guards>.
```

e.g. `"Bulk corpus capture, v0.6.7a0 crawl 2026-02-06. Sole carrier of
knowledge/unit_converter."` Keep the provenance clause free of private-repo names.
One record (`7049404a2dd6`) intentionally retains a `GOOGLE_ABUSE_EXEMPTION` URL
token as an artifact of how the crawler obtained an abuse exemption.

## Reproducing the corpus assessment

```bash
# 1. Profile every record: provenance, layouts, unique contributors, rarity
uv run python scripts/profile_fixture_corpus.py

# 2. Review distinct-type signature clusters (potential redundancy)
uv run python scripts/compare_drop_signatures.py

# 3. Corpus-integrity guard (drops absent, notes present, layouts + coverage intact)
uv run python scripts/verify_drops.py

# 4. After any change, confirm the tests pass
uv run pytest tests/test_parse_serp.py tests/test_parser_coverage.py \
  tests/test_ai_overview_legacy_sge.py -q
```
