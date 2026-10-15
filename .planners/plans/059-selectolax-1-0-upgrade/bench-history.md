# Parse benchmark history

Every recorded parse-timing run from the bs4 era through the selectolax 1.0
upgrade, gathered from plan Logs and `tests/benchmarks/results.jsonl` (compiled
2026-10-15).

**Source** says where each row comes from. A plan row is from that plan's Log
prose, written by hand with whatever fields that session chose to record. A
`results.jsonl` row is a structured record the bench writes itself, with every
field filled in (row numbers count from 1 in file order). The plan 059 rows are
in both places.

| Date | Source | Run | Parser | Python | SERPs | Iter x runs | Corpus ms/pass | Per-SERP median ms |
|---|---|---|---|---|---|---|---|---|
| 2026-05-24 | plan 023 | baseline | bs4 | ? | 66 | 8 x 3 | 10,269 | 134.2 |
| 2026-05-24 | plan 023 | `str(soup)` removed | bs4 | ? | 66 | 8 x 3 | 7,559 | 111.2 |
| 2026-05-24 | plan 023 | next item | bs4 | ? | 66 | 8 x 4 | 7,096 | 104.4 |
| 2026-05-24 | plan 023 | item 4a | bs4 | ? | 66 | 8 x 4 | 6,781 | 97.5 |
| 2026-05-24 | plan 023 | 4a re-run, drift check (`ef7d19f`) | bs4 | ? | 66 | ? | 6,983.8 | ? |
| 2026-05-24 | plan 023 | items 6b/6c/8 | bs4 | ? | 66 | ? | 6,958 | ? |
| 2026-05-27 | plan 026 | A/B before (`d4ead9e`) | bs4 | 3.13 | 60 | ? | 14,636 | 236.8 |
| 2026-05-27 | plan 026 | A/B after | selectolax via adapter | 3.13 | 60 | ? | ~7,175 | ~107-116 |
| 2026-05-29 | plan 026 / PR #138 | adapter baseline (`68b8423`) | selectolax via adapter | 3.13? | 60 | 20 x 3? | ? | 122.4 |
| 2026-05-29 | PR #138 | bs4 deps dropped | selectolax via adapter | 3.13? | 60 | 20 x 3 | ? | 117.9 / 124.7 / 128.2 |
| 2026-05-29 | plan 026 | adapter removed | selectolax native | 3.13 | 66 | 5 x 3 | ? | 72.6 |
| 2026-05-29 | plan 026 | final A/B before (`9e633bf`) | bs4 | ? | 66 | 50 x 2 | ~6,812 | ~98 |
| 2026-05-29 | plan 026 | final A/B after (`94bc682`) | selectolax native | ? | 66 | 50 x 5 | ~1,317 | 19.0 |
| 2026-06-01 | plan 035 | baseline | selectolax | 3.13.12 | 87 | 10 x 3 | 3,760.6 | 39.5 |
| 2026-06-01 | plan 035 | A/B before | selectolax | 3.13.12 | 87 | 10 x 3 | 3,872.0 | 39.9 |
| 2026-06-01 | plan 035 | A/B after (`get_text` fast path) | selectolax | 3.13.12 | 87 | 10 x 3 | 3,590.3 | 36.7 |
| 2026-06-05 | `results.jsonl` #1 | 0.9.0a0 | selectolax 0.4.10 (lock) | 3.14.3 | 80 | 50 x 5 | 1,437.9 | 16.75 |
| 2026-06-06 | plan 036 | baseline | selectolax | 3.14.3 | 87 | 50 x 5 | 1,516.1 | 15.35 |
| 2026-06-06 | plan 036 | lever 1 | selectolax | 3.14.3 | 87 | 50 x 5 | 1,502.3 | ? |
| 2026-06-06 | plan 036 | levers 1+3 | selectolax | 3.14.3 | 87 | 50 x 5 | 1,463.3 | ? |
| 2026-06-06 | `results.jsonl` #3 | 0.9.1a0 | selectolax 0.4.10 (lock) | 3.14.3 | 87 | 50 x 5 | 1,472.6 | 14.91 |
| 2026-06-11 | `results.jsonl` #5 | 0.10.0a0 | selectolax 0.4.10 (lock) | 3.14.3 | 87 | 50 x 5 | 1,493.1 | 14.48 |
| 2026-06-11 | `results.jsonl` #6 | 0.10.0a0 | selectolax 0.4.10 (lock) | 3.14.3 | 87 | 50 x 5 | 1,485.2 | 14.56 |
| 2026-07-10 | plan 056 | A/B before | selectolax | 3.14.3 | 102 | 40 x 5 | 1,598.1 | 13.19 |
| 2026-07-10 | plan 056 | A/B after (selector union) | selectolax | 3.14.3 | 102 | 40 x 5 | 1,575.8 | 12.81 |
| 2026-10-15 | `results.jsonl` #8 (059a) | 0.4.10 reference | selectolax 0.4.10 | 3.14.8 | 102 | 50 x 5 | 1,556.9 | 12.72 |
| 2026-10-15 | `results.jsonl` #9 (059a) | 0.4.13 baseline | selectolax 0.4.13 | 3.14.8 | 102 | 50 x 5 | 1,571.2 | 13.16 |
| 2026-10-15 | `results.jsonl` #11 (059d) | A/B/B/A: A1 | selectolax 1.0.0 | 3.14.8 | 102 | 50 x 5 | 827.5 | 6.70 |
| 2026-10-15 | `results.jsonl` #12 (059d) | A/B/B/A: B1 | selectolax 0.4.13 | 3.14.8 | 102 | 50 x 5 | 1,565.3 | 12.84 |
| 2026-10-15 | `results.jsonl` #13 (059d) | A/B/B/A: B2 | selectolax 0.4.13 | 3.14.8 | 102 | 50 x 5 | 1,573.1 | 13.00 |
| 2026-10-15 | `results.jsonl` #14 (059d) | A/B/B/A: A2 | selectolax 1.0.0 | 3.14.8 | 102 | 50 x 5 | 828.4 | 6.77 |

## Notes

- `?` means the source did not record the value. `3.13?` is inferred from the
  plan's use of a Python 3.13 venv, not stated.
- "selectolax 0.4.10 (lock)": these rows predate the bench's
  `selectolax_version` field; the value is what `uv.lock` pinned at the row's
  commit, not a recorded installed version.
- The six profile-only rows in `results.jsonl` (#2, #4, #7, #10, #15, #16) are
  left out: they record total profiled seconds, not pass timings.
- Every run before 2026-10-15 ran under the bench's gc leak (fixed in 059a),
  which read about 10-15% high relative to the 059 rows.
- Only rows from one same-session A/B compare cleanly. Corpus size (60/66/80/
  87/102 SERPs), Python (3.13 to 3.14.3 to 3.14.8), iteration counts, and the
  gc fix all change across sessions.

## Readings

- **bs4 to selectolax:** the plan 026 final A/B (`9e633bf` vs `94bc682`, same
  66 SERPs and machine) is the clean comparison: about 98 to 19.0 ms/SERP,
  about 5.2x. The 0.9.0 CHANGELOG's "~2x" came from the 2026-05-27 A/B, whose
  bs4 side (236.8 ms on a 60-SERP subset) is an outlier against the other bs4
  runs (97.5-98 ms), and whose selectolax side still ran through the adapter.
- **The "122.4 ms bs4 baseline" is not bs4.** Plan 026's Log calls it that,
  but PR #138 places `68b8423` after the backend moved to selectolax, so it is
  the adapter build. The `convert-bs4-to-selectolax` skill's "~3.4x (122 ms to
  36 ms)" inherits the mislabel: it is adapter to native, not bs4 to
  selectolax.
- **Unexplained drop between plans 035 and 036:** on the same 87-SERP corpus,
  3,760.6 ms/pass (Python 3.13.12, 10 x 3, 2026-06-01) to 1,516.1 ms/pass
  (3.14.3, 50 x 5, 2026-06-06), about 2.5x. Python 3.13 to 3.14 is the obvious
  candidate, but code and iteration counts changed too and no same-session
  check isolates it.
- **selectolax 0.4.13 to 1.0.0:** the 059d A/B/B/A, 1,569.2 to 828.0 ms (means
  of the pairs), -47.2%.
