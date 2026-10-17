---
id: 62
slug: goto-redirect-resolution
status: draft
branch: dev
created: 2026-10-16T18:11:24-07:00
concluded:
pr:
---

# Resolve /goto redirect tokens to target URLs

## Plan

**Problem.** In SERPs collected since 2026-10, every outbound link is an
opaque redirect, `/goto?url=<token>`, in place of the target URL. This holds in
every result type that links out (`general`, `perspectives`, `short_videos`,
`videos`, `images`, `local_news`, `discussions_and_forums`, ...). The parsers
are not at fault: they read the anchor's `href` as before, and the row is
typed correctly. But the `url` field no longer names the destination, so
domain- or URL-level analysis of current captures breaks. Captures from 2026-07
and earlier link directly.

It is not tied to the browser profile. The same-day cold capture shows it on
every real SERP (3 of 3; its other 2 records are captcha pages), as does the
warm-profile run (42 of 45 SERPs).

| Source | Rows with a `/goto` URL | `general` rows with `/goto` |
|---|---|---|
| 2026-10-15 warm-profile run, `data/demo-ws-v0.11.7a2-warm-profile/serps.json` (45 SERPs, local) | 786 | 343 of 346 |
| 2026-10-15 cold capture, `data/demo-ws-v0.11.7a2/serps.json` (5 records, local) | 90 | 18 of 18 |
| Fixture corpus, `tests/fixtures/serps.json.bz2` | 66, all in the four 0.11.7a2 records | 29 |

**What the token is.** URL-safe base64 of a small protobuf, `{1: 1, 2: <bytes>}`,
like the UULE location parameter (`WebSearcher/locations.py`). Unlike UULE,
field 2 is not readable. It is ciphertext in the Tink layout: a `0x01` byte and
a 4-byte key ID (the same in all 2,063 tokens seen), then the encrypted URL with
a random nonce. The same URL gets a different token on each render, and the
token's length tracks the URL's length. It cannot be decoded offline; the target
is only available from the redirect.

The anchor's `ping` attribute carries the same token (`/url?...&url=<token>`),
not the URL. The page carries some full URLs elsewhere, which cover a subset:

- `cite`, the displayed URL (domain plus a truncated breadcrumb), on 273 of the
  343 `/goto` `general` rows in the run, and on no other type;
- AI overview citation payloads, for cited sources (plan 060 maps those
  redirects);
- image-pack metadata (`"2003":[null,"<doc id>","<page url>","<title>",...]`),
  untested;
- ads, which still carry `adurl=`.

**Resolution works.** Requesting `https://www.google.com/goto?url=<token>`
without following redirects returns `302` with the full target URL in
`Location`. Cookies and a session are not needed.

A test on 2026-10-16 resolved all 2,063 unique tokens from the two 2026-10-15
captures:

- **Pace:** 10 requests per second, 4 worker threads, no cookies kept, in two runs
  (1,000, then 1,063). No blocking: every response was a `302` to a non-Google
  host. The run stops on the first `429`, a redirect to `/sorry/`, any other
  status, or a `Location` back into Google.
- **Latency:** median 35 ms, p95 41 ms, max 115 ms, with no slowdown over the run.
- **Correctness:** all 234 tokens with a known target from the AI overview
  payloads matched exactly.
- **Age:** tokens 31-34 hours old still resolved. How long they stay valid is not
  known.
- **Output:** 1,494 unique URLs across 45 SERPs, all full URLs (scheme, host,
  path, and query where present). 82 of the first 1,000 end in a
  `#:~:text=` highlight fragment, which needs stripping before comparing URLs.

The sidecar `resolve_goto.py` is the test script. It is resumable: it appends
each result to `pairs.jsonl` and skips tokens already recorded. Each line holds
`token`, `url`, `resolved_at`, `elapsed_ms`, `serp_id`, `captured`, `source`, and,
where the payloads gave one, `payload_url`.

```bash
P=.planners/plans/062-goto-redirect-resolution/resolve_goto.py
uv run python $P data/goto-resolve \
    data/demo-ws-v0.11.7a2-warm-profile/serps.json data/demo-ws-v0.11.7a2/serps.json \
    --limit 1000 --rate 10
```

The pairs and log from the test live in `data/goto-resolve/` (local, git-ignored).

**Goal.** Provide a resolver in the public `WebSearcher` API, so callers can turn
`/goto` URLs in parsed results into target URLs after collection. Parsing stays
offline: `parse_serp` keeps the raw `url` and never makes requests.

**Steps.**

1. **API shape.** Settle the open questions below. A starting point:
   - `ws.resolve_goto(tokens_or_urls, *, cache=None, rate=10.0, workers=4)`
     returns `{token: url}`. It accepts bare tokens or `/goto?url=` hrefs, stops
     at the first sign of blocking, and reports which tokens were left
     unresolved.
   - A cache interface (default: a JSON-lines file, as in the sidecar), so a
     token is resolved once.
   - A helper to fill parsed results, e.g. `ws.resolve_results(results, ...)`,
     which writes the target to a new field and leaves `url` untouched.
2. **Implementation.** Move the sidecar's logic into a module (e.g.
   `WebSearcher/resolvers.py`, exported via `__all__`), on `requests`, which is
   already a dependency. Strict pyrefly types; the blocking checks as a small
   pure function.
3. **Tests.** No network in CI. Unit tests for token and href parsing, the
   blocking checks, pacing, and cache resume, with `requests` mocked. A small
   committed fixture of token-URL pairs for the 145 tokens in the fixture
   corpus would let tests check the fill helper against real rows.
4. **Docs.** README usage (kept generic, per the README conventions), a
   CHANGELOG entry, and a note on the request load the resolver puts on the
   search host.
5. **Optional, separate PR:** a `ws-demo` subcommand that resolves a demo
   capture's tokens.

**Open questions.**

1. What does the resolved field on a result row get called (`resolved_url`?), and
   is it top level or in `details`? Should nested URLs (sources, hyperlinks
   in `details`) also be resolved?
2. Should `#:~:text=` fragments be kept, stripped, or both kept and stripped
   into separate fields?
3. How long do tokens stay valid? Resolve a capture again a week or more later
   and record the outcome here.
4. What rate is safe at scale? Two runs of about 1,000 tokens at 10 per second
   were not blocked; larger batches and other networks are untested.
5. Does the cache key on the token alone? Tokens are per render, so the same URL
   appears under many tokens; the cache never maps across tokens.
