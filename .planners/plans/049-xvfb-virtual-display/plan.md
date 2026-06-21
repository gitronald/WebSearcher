---
id: 49
slug: xvfb-virtual-display
status: active
branch: feature/xvfb-virtual-display
created: 2026-06-09T23:53:22-07:00
concluded:
pr: https://github.com/gitronald/WebSearcher/pull/175
---

# Run the browser backends without a GUI via an Xvfb virtual display

## Problem

The browser backends (`SeleniumDriver`, and the plan-039 PoCs `PatchrightSearcher` /
`ZendriverSearcher`) must run **headed** to evade Google's bot detection — plan 039 showed that
Chrome's headless mode is reliably blocked (`/sorry/` reCAPTCHA), and the block survives both
`--headless=new` and a UA stripped of the `HeadlessChrome` token, so it's a deeper
headless-fingerprint, not a one-flag fix. That makes the backends awkward to run on a headless
server, in CI, or in a container, where there is no `$DISPLAY`.

**Xvfb** (X Virtual Framebuffer) is the standard answer: an in-memory X11 display server that
lets Chrome run *genuinely headed* (no headless code path, no headless fingerprint) with no
monitor or GPU. This plan investigates and documents running the backends under Xvfb.

See [[browser-automation-alternatives]] (plan 039) for the evaluation that surfaced this — the
headless findings and the UA/`--headless=new` probes are in its Log.

## Plan (stub)

1. Confirm the approach end to end: install `xvfb`, run the patchright battery under
   `xvfb-run -a --server-args="-screen 0 1920x1080x24" uv run ws-demo searches patchright ...`
   on this machine with `DISPLAY` unset, and verify it clears Google (no `/sorry/`) with no
   visible window — the one piece plan 039 could not test (Xvfb was not installed).
2. Compare a real-display run vs. an Xvfb run for parse parity and any new fingerprint tell
   (software WebGL renderer — SwiftShader/llvmpipe — is the expected, milder signal).
3. Document the recommended server/CI invocation (env, screen geometry, `xvfb-run` vs. a managed
   `Xvfb :99`), and where it belongs in the docs. No code change is expected — it's an
   environment/launcher concern, independent of which backend is chosen.

## Evidence

Reproduce the headless block (from plan 039), then the Xvfb fix:

```bash
# Blocked: headless Chrome even with UA stripped + webdriver=False -> /sorry/
uv run python .claude/scratch/probe_headless_ua.py     # plan-039 scratch probe

# Proposed fix (needs `sudo apt-get install xvfb`): headed Chrome on a virtual display
env -u DISPLAY xvfb-run -a --server-args="-screen 0 1920x1080x24" \
  uv run ws-demo searches patchright --types general knowledge
```

## Out of scope

- IP reputation / rate limiting — the dominant Google-block factor regardless of display
  (needs residential/mobile proxies, not Xvfb).
- The browser-backend migration itself (plan 039 follow-up) and the `/sorry/` early-exit
  detection (plan 048, [[captcha-exit-on-sorry-redirect]]).

## Log

### 2026-06-21 — confirmed end to end on WSL2 (patchright)

Ran the experiment on this machine (WSL2 + WSLg, so `DISPLAY=:0` is a real GPU-backed
display; `xvfb` installed via `apt`). Backend: `patchright` (headed by default,
`headless=False`), single query `"why is the sky blue"`, `--no-ai-expand`, fresh
`tempfile.mkdtemp()` profile each run (held constant — both display conditions start cold).

Repro (the two invocations compared):

```bash
# Real WSLg display (baseline)
uv run ws-demo search "why is the sky blue" patchright --no-ai-expand --data-dir <out>/real

# Xvfb, DISPLAY unset, genuinely headed, no window
env -u DISPLAY xvfb-run -a --server-args="-screen 0 1920x1080x24" \
  uv run ws-demo search "why is the sky blue" patchright --no-ai-expand --data-dir <out>/xvfb
```

A-B-A-B' sequence (captcha flag = `features["captcha"]`, set by `utils.is_sorry_redirect`):

| run | display | result |
| --- | --- | --- |
| real  | WSLg `:0` (GPU)         | cleared, 33 results, `main_layout=standard` |
| xvfb  | virtual `:99` (sw GL)  | **`/sorry/` block**, `captcha=True`, 0 results |
| real2 | WSLg `:0`              | cleared, 33 results |
| xvfb2 | virtual `:99`          | cleared, **33 results, type histogram identical to `real`** |

**Findings:**

1. **Xvfb works** — patchright runs genuinely headed (no headless code path, no headless
   fingerprint) on a virtual display with `DISPLAY` unset and no window. Confirms the one
   piece plan 039 could not test.
2. **Parse parity** — a clearing Xvfb run is identical to the real-display baseline
   (`main_layout=standard`, 33 results, same per-type counts: `general` 8, `perspectives`
   12, `short_videos` 10, `ai_overview`/`people_also_ask`/`searches_related` 1 each).
3. **The `/sorry/` block is intermittent, not Xvfb-deterministic.** Real-display runs
   bracket the single block and clear, and a repeat Xvfb run clears with full parity — so the
   software WebGL renderer (SwiftShader/llvmpipe) is **not** a hard block trigger on this
   setup; the challenge is volume/IP-reputation driven (out of scope). The existing
   `ws-demo searches` CAPTCHA guard (detect `/sorry/`, wait 5 min, retry once) is the right
   mitigation.
4. **Bonus validation** — plan-048's URL-based `/sorry/` detection fired on the live block
   (`captcha=True`) and the timeout-capture saved the real `/sorry/` URL + HTML, confirming
   the 0.10.0 captcha work end to end against a genuine block.

**Recommended server/CI invocation** (still to be written into the docs — plan step 3):

```bash
env -u DISPLAY xvfb-run -a --server-args="-screen 0 1920x1080x24" \
  uv run ws-demo searches patchright --types general knowledge
```

`env -u DISPLAY` stops a fallback to a real display; `xvfb-run -a` auto-picks a free display;
`-screen 0 1920x1080x24` avoids a tiny-viewport tell. No code change needed — purely a
launcher/env concern. Caveats: small live sample (n=2 per condition); IP reputation remains
the dominant, separate factor (needs proxies, not Xvfb).
