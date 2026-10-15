---
id: 54
slug: persistent-user-data-dir
status: active
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
