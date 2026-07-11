---
id: 57
slug: logging-no-import-side-effect
status: active
branch: feature/logging-no-import-side-effect
created: 2026-07-11T13:30:52-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/193
---

# Stop configuring logging at import time

## Context

`import WebSearcher` mutates global logging state as a side effect. Ten modules
configure logging at module scope with `log = ...Logger().start(__name__)`:

- `WebSearcher/utils.py:18`
- `WebSearcher/locations.py:18`
- `WebSearcher/classifiers/main.py:9`
- `WebSearcher/extractors/__init__.py:10`
- `WebSearcher/extractors/extractor_header.py:7`
- `WebSearcher/extractors/extractor_rhs.py:5`
- `WebSearcher/extractors/extractor_footer.py:6`
- `WebSearcher/extractors/extractor_main.py:9`
- `WebSearcher/parsers/component.py:25`
- `WebSearcher/parsers/parse_serp.py:9`

`Logger.start()` calls `logging.config.dictConfig(...)`, whose loggers config attaches a
JSONL `StreamHandler` to the **root** logger (`""`) and sets root level to `DEBUG`. Because
`__init__.py` imports `classifiers`, `extractors`, `locations`, `parsers.parse_serp`, and
`utils`, all ten sites run on plain `import WebSearcher` — before any crawl starts and with
no config passed (default `console=True`).

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

1. **Remove the import-time side effect.** In all ten modules listed above, replace
   `log = logger.Logger().start(__name__)` with a plain module logger:

   ```python
   import logging
   log = logging.getLogger(__name__)
   ```

   No handler, no `dictConfig`, no root mutation. These modules keep logging exactly as
   before; they just no longer *configure* the logging system. Two mechanical
   consequences per module:

   - **Remove the now-unused import.** Each site's `from .. import logger` /
     `from ..logger import Logger` becomes unused, and ruff's pyflakes ("F", so F401)
     gates pre-commit and CI. In `locations.py` the import is combined — trim
     `from . import logger, utils` to `from . import utils` rather than deleting it.
   - **Drop dead loggers entirely.** Four modules (`locations.py`, `classifiers/main.py`,
     `extractors/extractor_header.py`, `parsers/parse_serp.py`) define `log` but never
     call it — delete the assignment (and skip `import logging`) there instead of
     converting dead code.

2. **Add a library `NullHandler`.** In `WebSearcher/__init__.py`, attach a no-op handler to
   the package logger:

   ```python
   import logging
   logging.getLogger(__name__).addHandler(logging.NullHandler())
   ```

   This is the standard library-author pattern: own only the package's named logger, leave
   root to the application. In Python 3 its effect is to suppress the `logging.lastResort`
   fallback (which would otherwise print WARNING+ records bare to stderr — the
   "No handlers could be found" message is a Python 2 artifact). This is a deliberate
   choice: with the `NullHandler`, parse-path warnings and errors (e.g. the
   `log.exception` in `parsers/component.py`) are **fully silent** until the application
   configures logging — matching the intent that the parse-only surface emits nothing.
   It covers all ten module loggers plus the crawl logger, since every one is named under
   the `WebSearcher.*` namespace.

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
  `SearchEngine` crawl) will now see no output — including warnings and parse errors, which
  the package `NullHandler` keeps from reaching `logging.lastResort` — until they configure
  logging themselves. The shipped `ws-demo parse`/`ws-demo show` subcommands lose their
  stderr JSONL error lines the same way (parse-error markers still land in the parsed
  rows). This is the intended, correct behavior for a library, but it is a visible change —
  call it out in the changelog as errors/warnings being silent until logging is configured,
  not just "no output".
- **Not a root-logger cleanup.** This plan does *not* stop `SearchEngine` from attaching its
  handler to the root logger at crawl time — that attachment is deliberate (it's how foreign
  logs are captured into the crawl-log schema). Moving WebSearcher off the root logger
  entirely would drop that foreign-log capture and is a separate, larger decision; out of
  scope here.

## Log

- 2026-07-11: Pre-implementation review (four lenses — mechanical completeness, in-repo
  reliance, downstream consumers, adversarial fix design — with per-finding adversarial
  verification). Corrections folded into the plan above:
  - The draft understated scope: **ten** module-scope `Logger().start(__name__)` sites,
    not two; all reachable from `import WebSearcher`. A package-wide sweep found no other
    import-time logging mutation (`parsers/bench.py`'s `setLevel` is function-scope; the
    crawl-time site in `searchers/searchers.py` stays by design).
  - Each converted module's `logger`/`Logger` import becomes unused; ruff F401 gates
    pre-commit and CI, so import cleanup is part of the change. Verified empirically by
    applying the replacement to scratch copies and running `ruff check`.
  - Four modules define `log` but never call it — the assignment is deleted there rather
    than converted.
  - Step 2's original rationale cited the Python 2 "No handlers could be found" fallback;
    the real Python 3 effect of the `NullHandler` is suppressing `logging.lastResort`,
    which makes parse-path warnings/errors fully silent for unconfigured applications
    (including `ws-demo parse`/`show` stderr error lines). Kept as a deliberate choice;
    rationale and changelog wording corrected.
  - No test, script, or doc in this repo relies on the import-time configuration (no
    caplog/handler assertions; benches pin their own level). A known downstream consumer
    pins a released tag, so the change reaches it only on a deliberate bump — and fixes
    the order-dependence bug (its `logging.basicConfig` is currently a silent no-op) that
    motivates this plan.
- 2026-07-11: Implemented on `feature/logging-no-import-side-effect` (commits `b53ab71`
  code, `4b2518e` changelog). All ten sites converted or deleted (four dead `log`
  assignments removed), unused `logger`/`Logger` imports dropped, `NullHandler` added in
  `__init__.py`. Verified: import leaves root handlers empty (root level back to default
  WARNING); a post-import `basicConfig` takes effect; a requests-backend `SearchEngine`
  still installs the JSONL console + file sinks and emits the crawl-log schema unchanged;
  643 tests and 102 snapshots pass; ruff and pyrefly clean. Draft PR opened.
