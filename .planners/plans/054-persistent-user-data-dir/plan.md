---
id: 54
slug: persistent-user-data-dir
status: draft
branch:
created: 2026-07-07T12:55:32-07:00
concluded:
pr:
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
