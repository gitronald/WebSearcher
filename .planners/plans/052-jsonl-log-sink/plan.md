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
- 2026-06-22 — Schema expansion (review feedback): added a structured `event` field
  to the JSONL schema and a **full event taxonomy** across every package log call
  (`search`, `search_config`, `parse`, `save_*`, `init_driver`, `browser_info`,
  `ai_expand`, `fetch`, `cleanup`, `delete_cookies`, `response`, `unzip`,
  `ssh_tunnel`). Rule: `event` is always set on WebSearcher log calls; `message`
  holds only the residual detail not encoded by `event`/fields and is `null` for
  pure event-marker lines (e.g. the search event, `search_config`). Added a
  `TextFormatter` that falls back to the `event` name when a record has no message,
  so the text console never shows a blank line (non-mutating: formats a copy, so a
  JSONL sink on the same logger still reads `message` as null). Final schema:
  `timestamp, pid, level, name, event, message, response_code, qry, loc, output`.
- 2026-06-22 — Logger name fix (review feedback): `SearchEngine` named its single
  shared logger with `__name__` -> the repetitive `"WebSearcher.searchers.searchers"`
  on every line. Switched to `__package__` -> `"WebSearcher.searchers"` (the operation
  now lives in `event`, so `name` only needs to identify the subpackage).
- 2026-06-22 — Dropped `name` from the JSONL schema (review feedback): it is constant
  for WebSearcher's own logs, so the structured sink omits it; it stays in the human
  text formatters (where `__package__` de-duplicated it).
- 2026-06-22 — Added a `source` field to track foreign log lines (review feedback):
  `source` is the originating logger name **only for non-WebSearcher records**
  (urllib3/requests/asyncio bubbling up to the root file handler), `null` for our own
  lines. `PACKAGE = __name__.split(".")[0]` gates it. This recovers attribution of
  propagated third-party WARNING noise without re-adding a constant name. Final schema:
  `timestamp, pid, level, event, message, response_code, qry, loc, output, source`.
- 2026-06-22 — Drop null fields from emitted records (review feedback): only
  `timestamp`/`pid`/`level` are always present; every other key appears only when
  non-null (`output` switched to null-when-absent so it drops too). A parse/save/
  foreign line no longer carries null `qry`/`loc`/`response_code`. Downstream
  consumers must read optional keys with `.get(...)`. The schema is now the *maximal*
  key set: `timestamp, pid, level, event, message, response_code, qry, loc, output,
  source`, of which each line emits the applicable subset.
- 2026-06-22 — Tag foreign logs `event: "external"` (review feedback): a non-WebSearcher
  record now gets `event="external"` alongside its `source` (the originating logger name),
  so third-party lines are filterable on either field. Ownership is decided by the logger
  name prefix (`WebSearcher`/`WebSearcher.*`), so a record's event extra is honored only
  for our own logs. Final schema unchanged.
- 2026-06-22 — Full suite: 555 passed, ruff + pyrefly clean.
