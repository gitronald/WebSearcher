---
status: done
branch:
created: 2026-02-22T12:56:12-08:00
completed:
pr:
---

# Structured Data Sources in Google SERP HTML

Research into what structured data exists in the HTML beyond the DOM elements
currently used by the parser. Based on analysis of all 52 SERPs in the v0.6.8
test fixture.

## Most useful

### 1. `speculationrules` script tag

- Present in **all 52 SERPs** (100%)
- Clean JSON in `<script type="speculationrules">` with prefetch URL lists
- Maps almost perfectly to organic/general results -- every spec URL appears in
  parsed output, with zero false positives
- Typically 7-16 URLs per SERP
- Non-organic types (short_videos, perspectives, ads, KP) are excluded
- Could serve as validation/fallback for organic URL extraction, or as a way to
  distinguish organic from non-organic results
- Limitation: just URLs, no titles, snippets, or other metadata

### 2. `data-attrid` attribute

- Labels knowledge panel facts with semantic paths:
  - `kc:/people/person:born`, `kc:/people/deceased_person:died`
  - `kc:/people/person:spouse`, `kc:/people/person:children`
  - `kc:/organization/organization:founded`, `kc:/organization/organization:headquarters`
  - `kc:/tv/tv_program:writers`, `kc:/tv/tv_program:first episode`
  - `ss:/webfacts:no_of_episod`, `ss:/webfacts:budget`
  - `DictionaryHeader`, `EntryHeader`, `SenseDefinition`, `Etymology`
- Stable semantic identifiers that don't depend on CSS class names
- Also labels AI Overview components: `SrpGenSumSummary` (generated summaries),
  `SGEAttributionFeedback` (AI Overview citations)
- Labels visual digest components: `VisualDigestFirstImageResult`,
  `VisualDigestWebResult`, `VisualDigestVideoResult`

### 3. `data-q` attribute

- Contains exact text of People Also Ask questions
- Consistently 4 PAA questions per SERP (plus one matching the original query)
- More reliable than extracting question text from nested DOM elements

### 4. `data-surl` / `data-curl` attributes

- Present on video result containers with direct YouTube/video URLs
- Paired with `data-eidt` (tracking ID)
- Consistent across SERPs that have video results

## Moderately useful

### 5. `data-fburl` attribute

- URLs on SGE/AI Overview citation elements
- Inconsistent: 0 in ~15/52 SERPs, up to 35 when present
- Only covers AI Overview sources, not organic results

### 6. `data-lpage` attribute

- Landing page URLs on featured snippet / rich result images
- Sparse: 0-3 per SERP

### 7. `jsdata` attribute

- Component IDs on result wrappers (e.g., `l7Bhpb`, `Dmybpc`)
- Identifies Google's JS component types
- Obfuscated naming, likely changes over time

## Not useful

- `data-async-fc` -- opaque base64 async fetch config
- `window.jsl.dh()` -- deferred HTML injection, same content as what's in the DOM
- `google.kEI`, `google.sn`, `google.kHL` -- page-level metadata only
- No JSON-LD, no `AF_initDataCallback`, no protobuf blobs with result metadata
