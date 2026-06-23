---
id: 52
slug: jsonl-log-sink
status: active
branch: feature/jsonl-log-sink
created: 2026-06-21T19:32:00-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/181
---

# Native JSONL crawl-log sink

## Context

WebSearcher writes its crawl log as pipe-delimited text (the `detailed` formatter).
Downstream collection tooling that consumes these logs currently has to parse that text
back into structured rows *after the fact* — reassembling multi-line tracebacks and coping
with a search-event message whose fields are emitted in nondeterministic order. This plan
adds a **native JSON-lines log sink** so WebSearcher emits one structured JSON object per
line directly, which removes the need for that after-the-fact parser on new crawls.

(Ported from a downstream tracker that scoped this work but where it never landed; the
implementation belongs in this repo.)

Current state — verify with the repro below:

- `WebSearcher/logger.py` registers only `minimal`/`medium`/`detailed` formatters; there is
  no JSONL formatter.
- `WebSearcher/models/configs.py` `LogConfig.file_format` defaults to `"detailed"`.
- `WebSearcher/searchers/searchers.py` (`self.log.info(...)`, ~line 110) logs the search
  event as a `set`-joined string, so field order is nondeterministic and empty fields drop.

```bash
grep -nE "formatters|Formatter" WebSearcher/logger.py
grep -n "file_format" WebSearcher/models/configs.py
grep -nA1 "self.log.info" WebSearcher/searchers/searchers.py
```

## Plan

### Target schema (one JSON object per line)

A structured crawl-log record, so native logs match the shape downstream tooling already
consumes: `timestamp` (ISO-8601, ms), `pid`, `level`, `name`, `message`, `response_code`,
`qry`, `loc`, `output` (formatted traceback, `""` when none).

### Changes

1. **`WebSearcher/logger.py`** — add a `JsonlFormatter(logging.Formatter)` that serializes
   each record to the schema above: ISO timestamp from `record.created`;
   `response_code`/`qry`/`loc` via `getattr(record, ..., None)`; `output` =
   `self.formatException(record.exc_info)` or `""`; `json.dumps(..., ensure_ascii=False)`.
   Register it in the `formatters` dict via the dictConfig `"()"` factory key. The existing
   `assert <format> in formatters` checks then validate `"jsonl"` automatically. Leave
   `minimal`/`medium`/`detailed` unchanged.
2. **`WebSearcher/searchers/searchers.py`** (the search-event `self.log.info(...)` call) —
   log structured fields instead of the set-joined string:
   `self.log.info("search", extra={"response_code": ..., "qry": ..., "loc": ...})`. Fixes
   the field-order ambiguity at the source. The error path already uses `log.exception(...)`,
   so `exc_info` flows into `output` unchanged.
3. **Docstrings** — `WebSearcher/logger.py` documents `console_format`/`file_format` as
   "Should be either 'minimal' or 'detailed'"; update both to list the full registered set
   (incl. `jsonl`). `LogConfig.file_format` itself needs no type change — it already accepts
   any registered formatter name.

### Decisions

- **Default stays `detailed`** (text); JSONL is opt-in via `file_format="jsonl"`.
- **Concurrency.** Workers append to one file (as today). A torn long line (error +
  traceback) would be a single invalid JSON line; typical JSONL readers skip bad lines. If a
  hard guarantee is wanted, route the file sink through a stdlib `QueueHandler` + single
  `QueueListener` so each line is written atomically. Decide during implementation.

### Testing

- Unit: `JsonlFormatter` emits valid JSON with the full key set; `exc_info` → `output`; a
  non-search record has `response_code`/`qry` null.
- Emission: a search log call with `extra=` round-trips to `response_code`/`qry`/`loc`.
- Parity: the emitted keys match the target schema field names.

### Out of scope

- Legacy backfill — handled downstream by the existing after-the-fact log parser; this plan
  only adds the forward (native) path.
- The downstream config flip — downstream tooling switches its `log_config` to
  `{file_format: "jsonl", ...}` and retires its log parser for new crawls once WebSearcher
  ships the formatter. That change lives in the downstream repo, not here.

### Versioning

Minor bump (additive logging feature; default behavior unchanged).

## Log

- 2026-06-22 — Implemented on `feature/jsonl-log-sink` (PR #181). Added
  `JsonlFormatter` registered as `"jsonl"` via the dictConfig `"()"` factory key;
  `timestamp` is local tz-aware ISO-8601 with ms (`datetime.fromtimestamp(record.created).astimezone()`)
  so JSONL and text logs from the same crawl share a wall-clock. Added
  `tests/test_logger.py` (9 tests). Full suite: 543 passed, ruff + pyrefly clean.
- 2026-06-22 — Deviated from the spec's `self.log.info("search", extra={...})`:
  built `log_fields` once and used it for **both** a deterministic summary message
  (`" | ".join(...)`, drops empty fields) **and** the structured `extra=`. The
  spec's literal `"search"` message would have stripped response_code/qry/loc from
  the default `detailed` text logs; the summary keeps text logs informative while
  the JSONL sink still gets the full structured field set. Concurrency stayed on
  the plain `FileHandler` append (the QueueHandler option was not needed).
