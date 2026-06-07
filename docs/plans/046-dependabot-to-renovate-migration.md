---
status: active
branch: feature/renovate-migration
created: 2026-06-07T16:00:19-07:00
completed:
pr:
---

# Migrate dependency automation from Dependabot to self-hosted Renovate

## Plan

Replace WebSearcher's Dependabot dependency-update config with the self-hosted, security-hardened
Renovate setup that `proj-template` ships. This brings WebSearcher in line with the house default
(`proj-template/docs/plans/003-add-renovate.md`) — declarative release cooldown, per-ecosystem
grouping, ongoing SHA-pinning of actions, a least-privilege GitHub App token (so update PRs trigger
CI), and no auto-merge.

The two repo secrets the runner needs — `RENOVATE_CLIENT_ID` and `RENOVATE_APP_PRIVATE_KEY` — are
**already set on the WebSearcher repo** (the GitHub App is created and installed). This plan does
not create, read, or touch those secrets; it assumes they are correct. What remains is committing
the config/workflow, removing Dependabot's *updates* config, normalizing the Dependabot repo
settings so only Renovate opens PRs, and the first run.

### Source of truth

The payload to copy comes from `proj-template/template/.github/`:

- `renovate.json` — Renovate config (`config:recommended` + `helpers:pinGitHubActionDigests`,
  5-day cooldown, grouping, digest-mutation block on workflows).
- `workflows/renovate.yml` — scheduled self-hosted runner (weekly cron + `workflow_dispatch`),
  mints a least-privilege App token from the two secrets.

The decision record and security rationale live in
`proj-template/docs/guides/github-automation.md` (the shipped `renovate.json` `description` points
back to it). Read both before implementing — the security defaults are non-optional and grounded in
GitGuardian's *Renovate & Dependabot: The New Malware Delivery System*.

### Two WebSearcher-specific adaptations (vs. a scaffolded repo)

A repo scaffolded from the template has default branch `dev`; **WebSearcher's default branch is
`master`** (release-only — see `.claude/skills/versioning/SKILL.md`). Two consequences:

1. **Activation routing — the workflow must reach `master`.** GitHub only runs a `schedule` /
   `workflow_dispatch` workflow from the file as it exists on the **default branch**. So
   `renovate.yml` must be on `master` before Renovate can run *at all* (cron *or* manual dispatch).
   Decision (confirmed): land the Renovate files on a dedicated infra branch cut from `master` and
   merge it to **both `master` and `dev` now**, independent of the in-flight `0.10.0` cycle — exactly
   as `test.yml` / `publish.yml` already live on `master` independent of any single feature release.
   This activates Renovate immediately instead of waiting for `0.10.0` to ship.

2. **Base-branch target — Renovate opens PRs against `dev`.** Decision (confirmed): keep the
   template default `baseBranchPatterns: ["dev"]`. Dependency-update PRs land on the permanent
   between-cycle integration branch (`dev`) and ride a release to `master`, keeping `master`
   release-only. This is a behavior change from the current Dependabot, which targets the default
   branch (`master`). Because Renovate reads repo config from each base branch, `renovate.json` must
   exist **on `dev`** (the base target) **and on `master`** (the default branch the runner checks out
   and loads via `configurationFile:` as global config). The single infra branch merged to both
   branches satisfies this; the two committed copies are identical, so the global-config /
   repo-config merge is the benign no-op the `renovate.yml` comment documents.

### Files to change (in WebSearcher's `.github/`)

- **Remove** `.github/dependabot.yml` — Dependabot's *version-updates* role is replaced by Renovate.
  (Dependabot vulnerability **alerts** are a repo setting, not this file — they stay on; see below.)
- **Add** `.github/renovate.json` — copied verbatim from
  `proj-template/template/.github/renovate.json`. Keep `baseBranchPatterns: ["dev"]` and the
  `description` URL pointing at the proj-template guide. (Current content for reference:)

  ```json
  {
    "$schema": "https://docs.renovatebot.com/renovate-schema.json",
    "description": "Self-hosted Renovate config. Rationale and setup: https://github.com/gitronald/proj-template/blob/main/docs/guides/github-automation.md",
    "extends": ["config:recommended", "helpers:pinGitHubActionDigests"],
    "baseBranchPatterns": ["dev"],
    "minimumReleaseAge": "5 days",
    "minimumReleaseAgeBehaviour": "timestamp-required",
    "dependencyDashboard": true,
    "packageRules": [
      { "matchManagers": ["pep621"], "groupName": "python" },
      { "matchManagers": ["github-actions"], "groupName": "github-actions" },
      { "matchFileNames": [".github/workflows/**"], "matchUpdateTypes": ["digest"], "enabled": false }
    ]
  }
  ```
  (Copy the full file with its inline `description` strings, not this condensed form.)

- **Add** `.github/workflows/renovate.yml` — copied verbatim from
  `proj-template/template/.github/workflows/renovate.yml`. No edits needed: it already reads
  `${{ secrets.RENOVATE_CLIENT_ID }}` / `${{ secrets.RENOVATE_APP_PRIVATE_KEY }}` and uses
  `RENOVATE_REPOSITORIES: ${{ github.repository }}`, so it resolves to `gitronald/WebSearcher`
  automatically. Re-verify the two pinned action SHAs against upstream at implementation time
  (`actions/create-github-app-token` v3.2.0 → `bcd2ba49218906704ab6c1aa796996da409d3eb1`;
  `renovatebot/github-action` v46.1.14 → `693b9ef15eec82123529a37c782242f091365961`).
- **Leave** `.github/workflows/{test,publish}.yml` as-is. Renovate keeps their `uses:` SHA pins
  current via `helpers:pinGitHubActionDigests` (new/unpinned actions get pinned; same-tag digest
  re-pointing is blocked by the workflow rule). Note WebSearcher's `test.yml` already triggers on
  `push`/`pull_request` to `dev` (among others), so Renovate's PRs targeting `dev` run CI.

### Implementation order

1. **Branch off `master`** (not the integration branch — the change must land cleanly on `master`):
   `git switch master && git switch -c feature/renovate-migration`.
2. Add `.github/renovate.json` and `.github/workflows/renovate.yml`; remove `.github/dependabot.yml`.
3. **Validate `renovate.json` with the official validator** before committing — this is the lesson
   from proj-template plan 003 (it caught the `baseBranches`→`baseBranchPatterns` deprecation that
   doc/review passes missed):

   ```bash
   npx --yes --package renovate -- renovate-config-validator .github/renovate.json
   ```
   (`uv` is the Python runner; Renovate's validator is a Node tool, so `npx` is correct here.)
4. Commit (`add renovate config, retire dependabot updates`), push, open a PR to `master`, merge
   `--no-ff` once CI is green. This puts `renovate.yml` + `renovate.json` on the default branch so
   the cron/dispatch can run.
5. **Also merge the same branch into `dev`** (`--no-ff`) so `renovate.json` exists on the base target
   and `dependabot.yml` is removed there too. Because the branch was cut from `master` and only
   touches these three files, the merge into `dev` pulls no unrelated unreleased commits onto
   `master`, and only the three-file delta onto `dev`.
6. **Carry the same delta onto the active `feature/v0.10.0` cycle** so the in-flight branch isn't
   re-introducing `dependabot.yml` at its next release merge — merge `feature/renovate-migration`
   into `feature/v0.10.0` (or rebase the cycle on the updated `dev`/`master` per the normal flow).
7. Delete `feature/renovate-migration` after it has merged to `master` and `dev`.

### Post-merge enrollment (one-time, manual `gh` — needs repo admin)

Secrets are already set, so the only remaining repo-settings step is normalizing Dependabot so it
doesn't also open PRs, then the first run. These mirror `proj-template/scripts/renovate-enroll.sh`
steps 2–3 (step 1, pushing secrets, is already done). Run under your own `gh` auth (the App
deliberately lacks repo admin):

```bash
# Keep Dependabot vulnerability ALERTS on (advisory surface Renovate also reads):
gh api -X PUT /repos/gitronald/WebSearcher/vulnerability-alerts
# Turn Dependabot SECURITY-UPDATE PRs off so the two bots don't both PR the same CVE:
gh api -X DELETE /repos/gitronald/WebSearcher/automated-security-fixes
# First Renovate run (or wait for the Monday 06:00 UTC cron):
gh workflow run renovate.yml --repo gitronald/WebSearcher
# Watch it:
gh run list --repo gitronald/WebSearcher --workflow renovate.yml
```

Desired end state: Dependabot **alerts on**, Dependabot **security-update PRs off**, Renovate owns
all dependency PRs (routine + security). Do **not** delete the `dependabot.yml` repo any differently
than committing its removal — alerts and security-fix settings are repo settings, independent of the
file.

### Clean up the in-flight Dependabot PR

There is one open Dependabot PR — **#156** (`build(deps): bump the python group with 3 updates`,
branch `dependabot/uv/python-bfdfbfec47`). After cutover, close it and delete its branch; Renovate
will re-raise any still-relevant bumps under its own grouping/cooldown:

```bash
gh pr close 156 --repo gitronald/WebSearcher --delete-branch \
  --comment "Superseded by Renovate migration (plan 046); Renovate will re-raise as needed."
```

### Precondition to verify (do not change secrets)

The GitHub App backing the two secrets needs **Workflows: Read and write** permission if Renovate
should keep the `uses:` pins in `test.yml` / `publish.yml` current (the `github-actions` group writes
under `.github/workflows/`). The secrets/App are assumed correctly set up; just confirm this one
permission so the `github-actions` group isn't silently a no-op. If the App lacks it, Renovate still
manages the `pep621` Python group — only workflow-action bumps are affected.

### Docs

- Add a `CHANGELOG.md` `[Unreleased]` entry (Keep a Changelog format) noting the move from Dependabot
  to self-hosted Renovate for dependency updates.
- No new guide in WebSearcher — the canonical reference is the proj-template guide the `renovate.json`
  `description` links to. (If `proj-template` is later renamed to `templatehub`, that URL needs the
  sweep; out of scope here, GitHub auto-redirects in the meantime.)

### Security defaults inherited (do not weaken)

Carried verbatim from the template, grounded in the GitGuardian writeup — keep all of them:

- **5-day cooldown** (`minimumReleaseAge: "5 days"` + `minimumReleaseAgeBehaviour:
  "timestamp-required"`, fail-closed: timestamp-less updates held "Pending" on the dashboard).
- **No auto-merge** — every bot PR requires human review (the central mitigation; the axios incident
  auto-merged 95 PRs with no human).
- **No silent digest mutation in workflows** — `digest` update type disabled for
  `.github/workflows/**`; visible version bumps still flow.
- **Least privilege** — `GITHUB_TOKEN` stays `contents: read`; Renovate authenticates with the scoped
  App token; never `pull_request_target`.
- **CI on bot PRs** — the App token makes Renovate's PRs trigger `test.yml` (PRs opened with
  `GITHUB_TOKEN` don't); require green CI before merge.

## References

- proj-template Renovate plan: `proj-template/docs/plans/003-add-renovate.md`
- proj-template payload: `proj-template/template/.github/{renovate.json,workflows/renovate.yml}`
- proj-template guide (canonical decision record):
  `proj-template/docs/guides/github-automation.md`
- proj-template enroll tooling (mirrors the post-merge `gh` steps):
  `proj-template/scripts/renovate-enroll.sh`, `.claude/skills/renovate-enroll/SKILL.md`
- GitGuardian — Renovate & Dependabot: The New Malware Delivery System:
  <https://blog.gitguardian.com/renovate-dependabot-the-new-malware-delivery-system/>
- Renovate docs: <https://docs.renovatebot.com>
