---
id: 49
slug: xvfb-virtual-display
status: draft
branch:
created: 2026-06-09T23:53:22-07:00
concluded:
pr:
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
