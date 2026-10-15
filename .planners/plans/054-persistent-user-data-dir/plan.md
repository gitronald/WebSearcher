---
id: 54
slug: persistent-user-data-dir
status: implemented
branch: feature/persistent-user-data-dir
created: 2026-07-07T12:55:32-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/201
---

# Support a persistent user-data-dir for warm browser profiles

## Plan

**Motivation.** The patchright backend starts cold on every run: `init_driver`
falls back to a fresh `tempfile.mkdtemp` profile when `user_data_dir` is unset
(`WebSearcher/searchers/patchright_searcher.py:49-52`), and `send_request` calls
`delete_cookies()` in its `finally` on every request
(`patchright_searcher.py:139`). Each search therefore looks like a brand-new,
zero-history session, which Google challenges hardest — repeated `/sorry/`
CAPTCHA redirects. A stable, once-CAPTCHA-solved profile carries reputation
across runs and cuts the block rate.

**What already exists.** `PatchrightConfig.user_data_dir`
(`WebSearcher/models/configs.py:31`) is already plumbed through `init_driver`, so
the core capability is there — a caller can pass
`patchright_config={"user_data_dir": "..."}` today. The gaps are (a) the demos
don't expose it, and (b) cookie clearing defeats the trust a persistent profile
would accumulate.

**Scope.**
- Expose `--user-data-dir` on `ws-demo search` and `ws-demo searches`
  (`WebSearcher/demos/cli.py`, `WebSearcher/demos/search.py`), threaded into
  `SearchEngine(patchright_config={"user_data_dir": ...})`.
- Reconcile `delete_cookies()` with persistent profiles: decide whether to skip
  per-request cookie clearing when a `user_data_dir` is set (otherwise the warm
  profile still loses its cookie-based trust each request). Likely a
  `clear_cookies` toggle on `PatchrightConfig` defaulting to current behavior.
- Document the warm-profile workflow in the README (solve the CAPTCHA once by
  hand, reuse the dir).

**Open questions.**
- Default location for a persistent profile (e.g. `data/ws-profile/`) vs.
  requiring an explicit path.
- Whether a concurrent-run lock is needed (Chrome refuses to share a live
  profile dir across processes).

**Evidence / repro.** Diagnosed 2026-07-07: back-to-back `ws-demo search`
runs from this box returned `/sorry/index?continue=...&sei=...` blocks with
`response_code: 200` and no `#search`. A/B (`chromium_sandbox` True vs. False)
blocked identically, ruling the sandbox flag out; the trigger is cold-session
IP/session reputation. Grounding snippet:

```bash
uv run ws-demo search "why is the sky blue" patchright --data-dir .claude/scratch/probe
uv run python -c "import json,pathlib; r=json.loads(pathlib.Path('.claude/scratch/probe/serps.json').read_text().splitlines()[-1]); print(r['url'], r['response_code'], 'id=\"search\"' in r['html'])"
```

## Log

- **2026-10-15T09:00:23-07:00** — Activated.
  - Branch: `feature/persistent-user-data-dir`
  - Base: `dev` at `21ee414`
  - Worktree: `.worktrees/persistent-user-data-dir`
  - PR: pending
- **2026-10-15T09:04:21-07:00** — PR opened: https://github.com/gitronald/WebSearcher/pull/201
- **2026-10-15T09:04:21-07:00** — Implemented.
    - Open question 1 (default location): resolved to the OS per-user data dir via `platformdirs` (`utils.default_user_data_dir()`, e.g. `~/.local/share/WebSearcher/profile`), per the user's direction that the profile live in the standard place for browser profiles rather than in the repo. An explicit path still works; the CLI's bare `--user-data-dir` uses the default.
    - Open question 2 (concurrent-run lock): not needed. A local probe launched two headless Chrome processes on one profile dir; the second fails at once with `Failed to create a ProcessSingleton for your profile directory`. Documented in the README instead of adding a lock.
    - Cookie clearing: `PatchrightConfig.clear_cookies` defaults to `True` (unchanged behavior for library callers); the demos set it `False` whenever `--user-data-dir` is given.
    - Tests: `tests/test_profiles.py` includes a real headless-Chrome save/load round trip (cookie set, close, relaunch on the same dir, cookie present; temp-profile control shows no carry-over). No navigation; skips when Chrome cannot launch. Per the user, no live searches were run, so the warm-profile effect on CAPTCHA rate is not verified.
    - `tests/test_search_methods.py`'s `make_patchright` fixture (built via `__new__`) now sets a default `config`, since `send_request` reads `config.clear_cookies`.
- **2026-10-15T09:04:26-07:00** — Implemented: 6 commits ahead of `dev`.
- **2026-10-15T09:10:42-07:00** — Reactivated: back to active after review.
- **2026-10-15T09:10:42-07:00** — Review: default profile location changed.
    - Supersedes the open-question-1 resolution logged above. The OS per-user data dir hid a large, mostly disposable profile where it is rarely seen or cleaned, and the common browser tools (Selenium, Puppeteer, Playwright) default to temp profiles with no persistent default. The bare `--user-data-dir` now means `./.ws_profile` in the working directory, like `.venv` or `.pytest_cache`; `platformdirs` and `utils.default_user_data_dir()` are removed.
    - A profile directory WebSearcher creates gets a `.gitignore` of `*`, since it holds cookies; an existing directory is left untouched (`prepare_profile_dir` in `patchright_searcher.py`). Tested against a real `git status` in a temp repo.
    - Checks re-run on the branch: ruff, ruff format, pyrefly clean; 665 tests pass.
- **2026-10-15T09:10:44-07:00** — Implemented: 11 commits ahead of `dev`.
- **2026-10-15T09:49:49-07:00** — Reactivated: back to active after review.
- **2026-10-15T09:49:49-07:00** — Added `--leave-open` (user request after a manual warm-up test).
    - The user ran `ws-demo search --user-data-dir` from the worktree and solved the CAPTCHA within the demo's roughly 12-second `#search` wait, before the demo closed the browser. To keep the window open on demand, `ws-demo search`/`searches` now take `--leave-open`: the browser lives only as long as the process, so the CLI blocks on Enter before `close()`, and Ctrl-C or EOF also close it. Rejected with `requests`.
    - Tests in `tests/test_profiles.py` check that the prompt comes before the close (Enter, EOF, and Ctrl-C, for both commands) and that there is no prompt without the flag. README warm-up steps now use the flag.
    - Checks: ruff, ruff format, pyrefly clean; 673 tests pass.
- **2026-10-15T09:49:51-07:00** — Implemented: 16 commits ahead of `dev`.
- **2026-10-15T09:54:23-07:00** — Manual check by the user (not re-run by the session): with a profile warmed by solving one CAPTCHA by hand, `ws-demo search --user-data-dir` returned results with no CAPTCHA. Removing the profile brought the CAPTCHA back on the next search. A `ws-demo searches` batch run was started afterwards; its outcome is not recorded here.
- **2026-10-15T11:22:14-07:00** — Batch run by the user on the warmed profile (`ws-demo searches --user-data-dir --leave-open`), read back from the run's `serps.json` by the session. 40 queries in a row returned results over about 27 minutes at the default 30-second delay. The 41st of 48 ('election results') hit a `/sorry/` CAPTCHA, and the retry after the 5-minute wait was blocked again (429), so the batch stopped and `--leave-open` held the window at the Enter prompt as intended. Whether the query itself or the cumulative rate triggered the block is not known.
- **2026-10-15T11:35:29-07:00** — Close review (medium, /code-review on PR 201): no behavior bugs found; three cosmetic fixes in `8f60256`.
  - Review follow-up: raised a stray unwrapped paragraph in the README warm-profile section, a 156-char `searches()` docstring line, and a 101-char `--leave-open` help line; all fixed (docs and help text only, so no new tests; ruff, ruff format, pyrefly clean, 673 tests pass). Conscious no-ops, as intended behavior: `_close` is skipped on Ctrl-C mid-run (the atexit hook closes the browser), a pre-existing profile dir gets no `.gitignore`, `clear_cookies` stays `True` by default, and the `exists()`/`mkdir` race applies only to concurrent runs on one profile, which are unsupported.
