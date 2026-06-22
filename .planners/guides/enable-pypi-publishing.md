# Enable or disable PyPI publishing

The publish workflow (`.github/workflows/publish.yml`) runs when a `v*` tag is
pushed, but both of its jobs are gated on a repository **variable**
`PUBLISH_ENABLED`:

```yaml
if: vars.PUBLISH_ENABLED == 'true'
```

When the variable is unset or anything other than the string `"true"`, the tag
push still triggers the workflow but both jobs skip — nothing is built or
uploaded. This is a deliberate safety switch so an accidental tag (or a fork)
can't publish.

`PUBLISH_ENABLED` is a **variable**, not a secret: its value is non-sensitive
(just an on/off flag) and is fine to read back in plain text.

## Enable

Set the variable to `true` with the GitHub CLI:

```bash
gh variable set PUBLISH_ENABLED --body true --repo {user/repo}
```

Run it from inside the repo and you can drop `--repo`; the CLI infers it from
the checked-out remote:

```bash
gh variable set PUBLISH_ENABLED --body true
```

## Verify

```bash
gh variable list --repo {user/repo}
```

`PUBLISH_ENABLED` should appear with value `true`.

## Disable

Either flip it to a non-`true` value, or delete it (an unset variable counts as
disabled):

```bash
# Flip off without removing
gh variable set PUBLISH_ENABLED --body false --repo {user/repo}

# Or remove it entirely
gh variable delete PUBLISH_ENABLED --repo {user/repo}
```

## Notes

- **Requires admin rights.** Setting or deleting repository variables needs
  admin access, so `gh auth login` must be done as a user with that role.
- **Takes effect on the next tag.** The check runs at workflow-run time, so the
  variable gates *future* `v*` tag pushes — it does not retroactively publish a
  tag that was already pushed while publishing was disabled.
- **Re-running a skipped tag.** If a tag was pushed while disabled, enable the
  variable and then re-run the workflow for that tag from the Actions UI, or
  delete and re-push the tag.
