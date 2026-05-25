# WebSearcher: A Story Told in Commits

*A reading of 1,082 commits, from `Initial commit` to the present.*

![Commit activity over time](commit_activity.png)

WebSearcher is a tool for scraping and parsing Google search results. That one
sentence explains almost everything that follows — because the story of this
repo is really the story of one person trying to keep up with a webpage that
will not stop changing.

## Act I — Late nights and packaging fiddliness (2019)

The first commit lands at **01:39 in the morning** on August 14, 2019.
Eighteen minutes later: `Improve readme`. The tone for the next several years
is set immediately — this is a side-of-the-desk research tool, built in the
margins of the day.

The early commits are the universal first-weeks-of-a-Python-package experience:
`Long description`, then `Longer description`, then `Using newlines`, all in
service of getting the PyPI page to render. Somewhere in the version dance the
author bumps `0.1.2 → 0.1.2` (to the *same* version), and later ships
`0.1.8 → 0.1.9` **twice**. Nobody's watching yet, and it shows.

By December 2019 the real work announces itself: `Overhaul of component
classifier, add scholarly articles component`. The thing that WebSearcher will
spend its entire life doing — looking at a chunk of Google HTML and deciding
*what kind of result is this* — is already the beating heart of the project.

## Act II — The pandas wars and the arrival of collaborators (2020–2022)

2020 is the busiest early year (83 commits), and it contains the single
funniest sequence in the history:

> `11:44` — **adinagit**: `Pandas remove (#7)`
> `11:48` — **Ronald E. Robertson**: `Revert "Pandas remove (#7)" (#9)`

A contributor's PR to remove pandas is reverted **four minutes** after it
merges. (The first attempt to drop pandas was actually back in September 2019:
`Remove pandas dependency`. It did not take. Pandas would not be fully exorcised
from the core until **February 2026** — roughly six and a half years, and a
migration to polars, later. Some dependencies do not go quietly.)

This era is also when WebSearcher stops being a solo project. A small cast of
collaborators files in, each leaving a very human trace:

- **emmalurie** — one commit, maximally humble: `changed if if else to if elif else`.
- **Stefan McCabe** — `Accept path-like inputs in utils.py`.
- **dzheng2019** — a genuine maintainer stint across 2020–2021: `added a checks
  to prevent key error`, `removed emoji dependency`, parser updates.
- **adinagit** — author of the doomed pandas removal.
- **Jeffrey Gleason** (a.k.a. **jlgleason**) — the most substantial outside
  contributor, threading through 2021–2024: `New Types (e.g. shopping_ads)`,
  knowledge subtypes for `flights, hotels, events`, and the wonderfully
  weary `small fixes for 2023/24 data`.

2021 and 2022 are the quiet years — 45 and 30 commits. The longest silence in
the whole history is a **155-day gap** in 2021. WebSearcher breathes on the
academic calendar: it goes dormant between the projects that need it, then
roars back when a new paper or a new Google layout demands it.

## Act III — The versioning identity crisis (early 2023)

For a few months in 2023, the project tries on calendar versioning for size:
`Bump to 2023.01.04`, `Bump to 2023.01.06`, then a curious string of
`2023.01.27-a`, `-b`, `-c`, `-d` (a date-stamped version that itself needed
four patch letters — the date stopped meaning the date). By mid-2023 it quietly
returns to semantic versioning at `0.3.x`, and never speaks of it again.

## Act IV — The renaissance (2023–2024)

Something changes in 2023: commits triple to 131, then nearly double again to
**227 in 2024**. This is the great rewrite. The parser stops being a pile of
functions and becomes an architecture:

- `update: rewrite extractors as class that tracks and passes along Component classes`
- `update: restructure parser to use component classes`
- `update: refactor notices parser as class`

And running underneath it all, the **eternal struggle of a SERP scraper**:
Google keeps redesigning the page.

- `add: initial extract from left-bar layout`
- `small fixes for 2023/24 data`
- `restore knowledge_panel cmpt-attr check to jscontroller qTdDb`

That last one is the whole job in a single line. WebSearcher's correctness
depends on Google's obfuscated class names like `qTdDb` — strings with no
meaning that can vanish in any silent A/B test, taking a parser with them.

## Act V — The AI Overview era (2025–2026)

2025 brings a tooling reckoning — **poetry → uv**, type hints modernized to
3.10+ syntax, selenium reorganized into a `searchers/` directory — and a brief
flip-flop captured perfectly by an outside contributor, **EvanUp**:
`switching from requests to selenium`. The two collection backends have been
in a tug-of-war for years.

Then 2026 explodes: **339 commits and counting**, already the most active year
in the project's life, with the single busiest quarter ever. The reason is in
nearly every message: **AI Overviews**. Google bolted a generative answer box
onto the top of the page, and WebSearcher has been reverse-engineering it ever
since:

- `add legacy sge markup support to ai_overview parser`
- `enrich ai overview with payload-sourced citations and richer sources`
- `record unavailable ai_overview state for declined overviews`

This is also the era of **plan-driven development** (plans 021 through 025), a
**dependabot swarm** (seven dependency-bump PRs merged in one morning on
2026-05-24), and — fittingly — the project's first commit authored by an AI:

> `2026-05-10` — **Claude**: `docs(plans): add 017 parse pipeline optimization plan`

## The toil and the anguish

Every long-lived codebase has its scar tissue. WebSearcher's reads like a diary
of small defeats:

- `fix return in finally in requests_searcher`, followed later by
  `move return out of finally block to fix syntax warning` — the same `finally`
  block, wrestled twice.
- `fix: drop debug print and fix print var` — the debug `print` that escaped
  into a commit, as it always does.
- `fix: 'None' passed as location again` — note the **`again`**. The bug came
  back.
- `update: ignore annoying dropbox file` — the adjective says everything.
- `Update header_text en español v2.py` — a source file committed with a space
  *and* a `v2` *and* the word "español" in its name. Somewhere, a linter wept.

## The cast

| Author | Commits | Note |
|---|---|---|
| gitronald / Ronald E. Robertson | 932 + 85 | The author; one identity, two git names (the second from GitHub merge buttons) |
| dependabot[bot] | 38 | Tireless, never sleeps, occasionally swarms |
| jlgleason / Jeffrey Gleason | 7 + 3 | The most substantial human collaborator |
| dzheng2019 | 7 | The 2020–2021 maintainer stint |
| wanLo | 2 | External HTML loading, `bs4` package-name fix |
| EvanUp | 2 | requests → selenium, AI overview expansion |
| Andrew Schwartz | 1 | Post-review pass |
| emmalurie | 1 | `if if else` → `if elif else` |
| Stefan McCabe | 1 | Path-like inputs |
| mariaelissat | 1 | The Spanish header strings |
| Claude | 1 | The first robot contributor |

## The moral

A SERP parser is a structure built on sand: the ground (Google's HTML) shifts
without warning, and the only response is another commit. WebSearcher's history
isn't a smooth climb — it's long quiet stretches punctuated by frantic bursts,
each burst triggered by Google shipping a new layout, a new card type, or a
whole new AI answer box. Seven years in, the activity chart is pointing
straight up, which means the work is nowhere near done. It never will be.

---

*Artifacts in this directory:*
- `get_commits.py` — dumps every commit to `commits.csv` (hash, timestamp, message)
- `plot_activity.py` — renders `commit_activity.png` (commits per quarter)
- `commits.csv` — the raw data this story was read from
- `commit_activity.png` — the activity chart above
