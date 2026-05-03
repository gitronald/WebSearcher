# Changelog Guide

`CHANGELOG.md` follows the [Keep a Changelog](https://keepachangelog.com/en) convention. That link redirects to the current version of the spec. This document serves as a summary of that standard. Here's what the website says about changelogs:

> #### What is a changelog?
>
> A changelog is a file which contains a curated, chronologically ordered list of notable changes for each version of a project.
>
> #### Why keep a changelog?
>
> To make it easier for users and contributors to see precisely what notable changes have been made between each release (or version) of the project.
>
> #### Who needs a changelog?
>
> People do. Whether consumers or developers, the end users of software are human beings who care about what's in the software. When the software changes, people want to know why and how.

— [Keep a Changelog](https://keepachangelog.com/en)

## File layout

- One `CHANGELOG.md` at the repo root
- Newest version at the top
- An `## [Unreleased]` section above the latest release, accumulating changes in flight
- Below that, one section per released version

## Version headings

Use the format:

```
## [VERSION] - YYYY-MM-DD
```

- The version is wrapped in square brackets so it can later be linked to a tag/diff
- The date follows ISO-8601 (`YYYY-MM-DD`)
- Pull dates from `git for-each-ref --sort=-creatordate refs/tags` — don't guess
- For prereleases (e.g. `0.7.1a1`), nest under `## [Unreleased]` as `### [VERSION] - DATE`
- For untagged or grouped historical entries, omit the date or use a range (e.g. `## [0.4.2] - [0.4.8] - 2024-11-11 to 2025-02-03`)

## Change types

Group bullets under the recommended subheadings when the entry has enough content to warrant grouping:

- `### Added` — new features
- `### Changed` — changes in existing functionality
- `### Deprecated` — soon-to-be-removed features
- `### Removed` — removed features
- `### Fixed` — bug fixes
- `### Security` — vulnerability patches

For small entries, a flat bullet list under the version heading is fine.

## Writing entries

- Lead with the impact, not the implementation detail
- Mark API breaks explicitly (e.g. `**Breaking:**` prefix)
- Link PRs and issues where they add context
- Keep prose terse; the reader is scanning, not studying

## Versioning

This project follows [Semantic Versioning](https://semver.org/). Alpha/beta/rc suffixes (`0.7.1a1`, `0.7.1b0`, `0.7.1rc1`) live under `[Unreleased]` until promoted to a stable release.

## Maintenance

- Add entries to `[Unreleased]` as work lands on `dev`
- On release, rename `[Unreleased]` → `[VERSION] - DATE` and start a fresh empty `[Unreleased]` above it
- Don't rewrite history — old entries should stay verbatim even if phrasing now feels rough
