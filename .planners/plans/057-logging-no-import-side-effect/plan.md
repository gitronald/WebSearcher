---
id: 57
slug: logging-no-import-side-effect
status: draft
branch:
created: 2026-07-11T13:30:52-07:00
concluded:
pr:
---

# Stop configuring logging at import time

## Context

`import WebSearcher` mutates global logging state as a side effect. Two modules
configure logging at module scope:

- `WebSearcher/utils.py:18` — `log = logger.Logger().start(__name__)`
- `WebSearcher/locations.py:18` — `log = logger.Logger().start(__name__)`

`Logger.start()` calls `logging.config.dictConfig(...)`, whose loggers config attaches a
JSONL `StreamHandler` to the **root** logger (`""`) and sets root level to `DEBUG`. Because
`__init__.py` imports from both `utils` and `locations`, this runs on plain
`import WebSearcher` — before any crawl starts and with no config passed (default
`console=True`).

Consequences for any application that imports the package:

- Its root logger is reconfigured to emit WebSearcher's JSONL format to stderr, whether it
  wants that or not.
- Order-dependence: whoever configures root first wins. If the app imports WebSearcher
  before its own `logging.basicConfig(...)`, that `basicConfig` becomes a silent no-op (it
  only acts when root has no handlers). If it configures root after import, it can get
  duplicate handlers and doubled lines.
- Root level is forced to `DEBUG`, raising verbosity for every other library in the process.

There is already a legitimate, crawl-time configuration point:
`WebSearcher/searchers/searchers.py:56` — `SearchEngine.__init__` calls
`logger.Logger(**self.config.log.model_dump()).start(__package__)`. That is where logging
*should* be configured (when a crawl actually runs), and it stays. The parse-only surface
(`parse_serp`, `load_html`, classifiers, extractors) should emit nothing until an
application configures logging itself.

Repro:

```bash
uv run python -c "import logging; import WebSearcher; print(logging.getLogger().handlers)"
# prints a StreamHandler with WebSearcher's JsonlFormatter — should be []
```

## Plan

1. **Remove the import-time side effect.** In `utils.py` and `locations.py`, replace
   `log = logger.Logger().start(__name__)` with a plain module logger:

   ```python
   import logging
   log = logging.getLogger(__name__)
   ```

   No handler, no `dictConfig`, no root mutation. These modules keep logging exactly as
   before; they just no longer *configure* the logging system.

2. **Add a library `NullHandler`.** In `WebSearcher/__init__.py`, attach a no-op handler to
   the package logger so records emitted before any configuration don't trigger the
   "No handlers could be found" fallback:

   ```python
   import logging
   logging.getLogger(__name__).addHandler(logging.NullHandler())
   ```

   This is the standard library-author pattern: own only the package's named logger, leave
   root to the application.

3. **Keep crawl-time configuration as-is.** `SearchEngine.__init__` remains the sole place
   that calls `Logger(...).start(...)`. A crawl still gets the full JSONL log (including the
   root-attached handler that captures foreign logs from `urllib3`/`requests`/`asyncio`),
   because that path is unchanged. The only thing removed is the *import-time*, unconfigured
   invocation.

4. **Verify.**
   - `import WebSearcher` leaves `logging.getLogger().handlers == []` (repro above).
   - A downstream `logging.basicConfig(...)` after `import WebSearcher` now takes effect.
   - Running an actual `SearchEngine` crawl still writes the JSONL crawl log unchanged.

## Downsides / trade-offs

- **Behavior change for import-time-only users.** Anyone who relied on `import WebSearcher`
  auto-configuring console logging (e.g. calling `utils`/`locations` helpers outside a
  `SearchEngine` crawl) will now see no output until they configure logging themselves. This
  is the intended, correct behavior for a library, but it is a visible change — call it out
  in the changelog.
- **Not a root-logger cleanup.** This plan does *not* stop `SearchEngine` from attaching its
  handler to the root logger at crawl time — that attachment is deliberate (it's how foreign
  logs are captured into the crawl-log schema). Moving WebSearcher off the root logger
  entirely would drop that foreign-log capture and is a separate, larger decision; out of
  scope here.
