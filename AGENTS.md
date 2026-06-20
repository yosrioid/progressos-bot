# Agent Instructions

## Working Style

- Communicate with the user in Indonesian unless they explicitly switch language.
- Keep changes scoped to the requested task.
- Do not bypass ProgressOS Laravel APIs or write directly to the ProgressOS database.
- Treat Telegram as the first channel adapter, not the whole product. Keep core parser, schemas, and ProgressOS client channel-neutral where practical.

## Code Rules

- Python target: 3.11+.
- Follow `docs/PYTHON_ENGINEERING_GUIDE.md` for structure, typing, security, testing, and code style.
- Run `make check` before handoff when dependencies are installed.
- Keep Pydantic schemas strict: use `extra="forbid"` for AI-facing payloads.
- Never send AI output to ProgressOS before local validation and explicit user confirmation.
- Do not log secrets, bearer tokens, full HTTP headers, or raw external API credentials.
- Prefer small, typed functions over broad framework-level abstractions.

## API Rules

- ProgressOS source of truth: `/api/v1/quick-capture` for capture writes.
- Use `Idempotency-Key` for retried write requests.
- Follow `docs/PHASES.md` when selecting the next feature slice.
- Read the current API notes before changing integration behavior:
  - `docs/PROGRESSOS_API_RESEARCH.md`
  - `docs/PROGRESSOS_API_CONTRACT.md`

## Verification

Use:

```bash
make check
```

If dev tools are not installed:

```bash
python3 -m pip install -e ".[dev]"
make check
```

When Python bytecode cache cannot be written outside the workspace, use:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/progressos-bot-pycache python3 -m compileall -q src tests
```
