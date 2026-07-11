---
id: 55
slug: label-as-details-field
status: draft
branch:
created: 2026-07-09T17:47:30-07:00
concluded:
pr:
---

# Emit ad and local result labels as a details field

## Plan

> Stub — problem outline only; flesh out scope + fixtures before implementing.

### Problem

When parsing `ad` (standard) and `local_results` components, the parsers extract
a short **label** from the DOM but then re-serialize it back into the result's
`text` as a pseudo-HTML `<label>…</label>` tag instead of surfacing it as
structured data. Two labels are affected:

- **Ad-funding disclaimer** — e.g. *"Paid for by …"* — from `span.mXsQRe`.
- **Place status label** — a short qualifier shown on a local result — from
  `span.X0w5lc`.

This is inconsistent with how every other structured signal is emitted (through
the `details` dict) and is effectively lossy: the label is folded into free-text
snippet content, so it both pollutes `text` and forces any consumer to re-parse
the tag out of the string to recover a clean value. There is no first-class field
for it.

### Affected parsers

| component | function | label source | current `details` | current `text` |
|---|---|---|---|---|
| `local_results` | `parse_local_result` (`parsers/components/local_results.py`) | `span.X0w5lc` | `{"type": "place", …}` | `f"{text} <label>{label}</label>"` |
| `ad` (standard) | `_parse_ad_standard_text` / `_parse_ad_standard_sub` (`parsers/components/ads.py`) | `span.mXsQRe` | ad submenu dict, or `None` | `f"{text} <label>{label}</label>"` |

Both build the `<label>…</label>` string in the same shape:
`f"{text} <label>{label}</label>" if label else text`.

### Direction

Emit the label as a proper field on the `details` dict at parse time (e.g.
`details["label"]`) and stop injecting `<label>…</label>` into `text`, so the
snippet text stays clean and the label is a first-class value.

### Open questions (resolve when implementing)

- **Field shape.** A plain `details["label"]` string, or a structured entry?
  Keep it uniform across the ad and local parsers.
- **`None` details.** The ad standard sub's `details` is the submenu, which is
  often `None`; a label with no submenu needs a details dict created for it. The
  local parser always has a `{"type": "place"}` dict, so it can just add the key.
- **`text` change.** Dropping the `<label>` wrapper changes `text` output for
  labelled ad/local rows — a parser-schema change. Update the affected
  fixtures/tests and bump the parser version accordingly.
- **Coverage.** Confirm these are the only two `<label>` construction sites
  (`grep '<label>'` currently finds exactly `local_results.py` and `ads.py`), and
  that no other component embeds a label this way.
