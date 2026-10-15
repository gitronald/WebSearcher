---
status: draft
branch:
needs: [a]
---

# Study the selectolax 1.0 release notes for our use

Part of [Upgrade selectolax to 1.0](../plan.md).

## Plan

Read the 1.0.0 release notes, and the 0.4.11-0.4.13 notes that step a pulls in,
against how WebSearcher actually uses selectolax. Classify every item, so c knows
what to change and d knows what to watch.

Sources: <https://github.com/rushter/selectolax/releases> (v0.4.11, v0.4.12,
v0.4.13, v1.0.0). Read them with
`gh release view <tag> -R rushter/selectolax --json body -q .body`.

### Classification

Each release-note item gets one label, with the call sites that justify it:

| Label | Meaning |
|---|---|
| n/a | we do not use the API it touches |
| free | we use it and gain without a code change (a speedup, a crash fix) |
| watch | we use it and its output may change; d checks it against the snapshot suite |
| adopt now | a small change in our code that the snapshot suite covers; c does it |
| follow-up | worth doing, but needs a parser refactor; a later plan does it |

The table goes in a `## Findings` section of this file, with one row per item.

### Checks to run

Cite the command or the `file:line` for each finding.

- **Removed APIs.** Confirm nothing in `WebSearcher/`, `tests/`, or
  `.claude/skills/` imports `selectolax.parser` (Modest) or calls
  `parse_fragment()`. Every import should be `selectolax.lexbor`.
- **Fragments.** We never pass `is_fragment=True`; `reparse_fragment` in
  `WebSearcher/_slx.py` re-parses a full document and takes `body`'s first
  element. Check whether the `head`/`body`/`root` staleness fixes touch that path
  (`notices.py` is its only caller).
- **Text.** `_slx._node_text` (`text(deep=False)`) and `_slx.get_text`
  (`text(deep=True, separator=..., strip=...)`) are the hot text paths. Check
  whether any caller passes `skip_empty`, whether the fixtures contain bytes that
  would now become U+FFFD, and how much of the a profile the 5x `text()` speedup
  can reach.
- **Attributes.** Find every `attrs`/`attributes` read that could see a namespaced
  attribute (`xlink:href` on SVG `<use>`), and count them in the corpus:
  `uv run python` over `tests/fixtures/serps.json.bz2`, counting `xlink:` in the
  stored HTML. Note where `attrs.items()`/`.values()` are used (now faster).
- **Mutation and iteration.** List the helpers and parsers that remove, unwrap, or
  decompose nodes, or iterate while mutating, against the `iter()` and `unwrap()`
  fixes.
- **Node equality.** Find `==` comparisons of nodes (for example in the
  `subtree_first`/`subtree_css` self-exclusion), which gain from the faster
  `__eq__`.
- **Selector helpers.** Note any use of `css_matches`, `any_css_matches`,
  `scripts_contain`, `script_srcs_contain`, `select()`, `traverse()`,
  `merge_text_nodes()`, or `text_lexbor`.
- **Workarounds that become dead.** Look for `UnicodeDecodeError` handling or other
  guards around selectolax quirks that 1.0.0 fixes upstream.
- **Typing.** Diff the shipped `.pyi` stubs between 0.4.13 and 1.0.0 for signature
  changes that pyrefly's strict preset would flag.
- **Wheels.** Confirm PyPI has 1.0.0 wheels for cp312, cp313, and cp314 on linux,
  macOS, and Windows, matching the CI matrix.
- **New API.** Assess `LexborHTMLParser(..., encoding=True)` against how
  `make_soup` receives `bytes`.

### Done when

The Findings table covers every item in the four releases' notes. Each `adopt now`
row names the change for c, each `watch` row names the component types for d to
inspect, and each `follow-up` row is listed in the umbrella's Log as a candidate
plan.

## Log
