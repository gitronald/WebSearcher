---
status: inactive
branch:
completed:
pr:
---

# Investigate missing URLs in the results_for local results variant

The `results_for` sub_type of `local_results` omits a URL in ~60% of cases (6 of 10 in the fixture corpus), while the other sub_types (`places`, `locations`) extract URLs at 100%.

## Plan

Retired without code changes — the gap is a server-side HTML omission, not a parser bug.

- In the empty cases the `.VkpGBb` card carries only a `role="button"` anchor (`jsname="kj0dLd"`) with no `href`; the Website/Directions anchors (`a.L48Cpd`, `a.Q7PwXb.VDgVie`) are simply absent from the markup.
- `_link_text_to_url()` (`WebSearcher/component_parsers/local_results.py:102`) correctly returns `None` when those anchors are missing, so there is nothing to fix at the source.

Decision: no parser change. At most, add a one-line comment near `_link_text_to_url()` noting that `results_for` URLs are only conditionally present in the HTML.

## Retrospective

This plan was added late — during v0.9.0 documentation finalization, long after the parser shipped — and resolved to "no change" the moment it was written; the corpus already proved the URLs are absent server-side. It records a decision, not forward work. Lesson: when a TODO item is really a known-limitation note, capture it as a code comment or a changelog caveat at the time, rather than carrying it as open work to be planned and retired later.
