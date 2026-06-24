# Release Checklist

Use this checklist before every tag.

## Target

- Confirm the tag target commit is on `main`.
- Confirm local `main` is clean and synced with `origin/main`.
- Record the tag name and target commit SHA in release notes.
- Confirm the release version matches `pyproject.toml` and `src/progressos_bot/version.py`
  when the package version changes.

## Verification

- Confirm the latest `main` CI run is green.
- Run `make check` locally with Python 3.11+ when dev dependencies are installed.
- If local Python is older than 3.11, use GitHub Actions as the release gate and record
  the green run URL.
- Run the dependency audit workflow manually before tagging when the scheduled run is
  older than seven days.
- Review open Dependabot PRs for Python and GitHub Actions updates.

## Supply Chain

- Keep workflow `permissions` minimal. CI and dependency audit should only require
  `contents: read`.
- Review third-party GitHub Actions before release. Current policy allows pinned major
  tags for official GitHub actions; switch to full commit SHA pins if release governance
  or deployment policy requires immutable action references.
- Review new or upgraded Python dependencies for license, maintenance status, and
  necessity before merging them.
- Do not include bearer tokens, webhook secrets, `.env` values, or raw request headers in
  changelog, release notes, logs, screenshots, or diagnostic bundles.

## Tagging

- Prefer signed tags when the release environment has signing keys configured.
- If signed tags are not available, record that decision in the release notes.
- Create the tag only after CI and dependency checks are complete.
- Include rollback notes: previous tag, config changes, and any migration or operational
  step needed to revert.
