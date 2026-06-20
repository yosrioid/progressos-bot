# Contributing

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Fill `.env` with local Telegram, Groq, and ProgressOS credentials.

## Development Checks

Run all checks:

```bash
make check
```

Individual checks:

```bash
make lint
make typecheck
make test
```

Format code:

```bash
make format
```

## Pull Requests

- Keep PRs focused.
- Include tests for parser, schema, or ProgressOS client changes.
- Update docs when changing AI contracts, ProgressOS payloads, or channel behavior.
- Explain verification commands and results in the PR description.
- Do not include `.env`, tokens, logs with secrets, or generated cache directories.

## Commit Style

Use concise imperative commit messages, for example:

```text
Add quick capture payload schema
```

