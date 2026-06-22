# Python Engineering Guide

This guide defines the project structure, code style, security posture, testing strategy,
and Python practices for ProgressOS Bot.

The defaults are based on commonly used Python practices and current project tools:

- Python 3.11+.
- `src/` layout.
- `pyproject.toml` for package and tool configuration.
- Ruff for linting and formatting.
- mypy in strict mode.
- pytest for tests.
- Pydantic for strict runtime validation.
- Environment variables or secret managers for secrets.

Reference materials:

- Python Packaging User Guide, `src` layout:
  https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- Python Logging HOWTO:
  https://docs.python.org/3/howto/logging.html
- mypy documentation:
  https://mypy.readthedocs.io/en/stable/
- Pydantic models and validation:
  https://docs.pydantic.dev/latest/concepts/models/
- OWASP Secrets Management Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

## Project Structure

Current structure:

```text
progressos-bot/
  .github/
    workflows/
      ci.yml
    pull_request_template.md
  docs/
    AI_CONTRACT.md
    PHASES.md
    PROGRESSOS_API_CONTRACT.md
    PROGRESSOS_API_RESEARCH.md
    PYTHON_ENGINEERING_GUIDE.md
    ROADMAP.md
    RULES.md
    SECURITY.md
  src/
    progressos_bot/
      ai/
        groq_client.py
        parser.py
        prompts.py
      channels/
        base.py
      core/
        capture_flow.py
        identity.py
        read_commands.py
      bot.py
      config.py
      logging.py
      main.py
      progressos_client.py
      schemas.py
  tests/
    test_message_parser.py
    test_payload_validation.py
  AGENTS.md
  CONTRIBUTING.md
  Makefile
  README.md
  pyproject.toml
```

Target structure as the project grows:

```text
src/progressos_bot/
  ai/
    client_protocol.py
    groq_client.py
    parser.py
    prompts.py
  channels/
    base.py
    telegram/
      adapter.py
      formatting.py
      handlers.py
  core/
    confirmation.py
    capture_flow.py
    identity.py
    idempotency.py
  progressos/
    client.py
    errors.py
    schemas.py
  observability/
    logging.py
    redaction.py
  config.py
  main.py
```

Structure rules:

- Keep importable code under `src/progressos_bot`.
- Keep tests under `tests`.
- Keep product and contract documents under `docs`.
- Channel adapters must not contain ProgressOS business rules.
- ProgressOS client code must not know Telegram-specific objects.
- AI parser code must not submit actions.
- Validation schemas should live near the boundary they protect.

## Module Boundaries

### `ai`

Owns:

- Prompt construction.
- Groq client integration.
- AI response parsing.
- AI contract enforcement before application logic uses the response.

Must not:

- Call Telegram.
- Call ProgressOS.
- Store pending confirmations.
- Decide final business authorization.

### `channels`

Owns:

- Telegram or future channel event handling.
- Channel-specific formatting.
- Channel confirmation UI.
- Mapping channel events into core flow calls.

Must not:

- Duplicate parser logic.
- Duplicate ProgressOS API logic.
- Trust display names as identity.

### `core`

Owns:

- Capture orchestration.
- Confirmation lifecycle.
- Identity mapping.
- Idempotency decisions.
- Cross-channel workflow behavior.

Must not:

- Import Telegram framework classes.
- Depend directly on Groq SDK details.

### `progressos`

Owns:

- HTTP client.
- ProgressOS request and response schemas.
- Error mapping.
- Retry-safe write behavior.

Must not:

- Build AI prompts.
- Render Telegram messages.

## Code Format

Use Ruff as the formatter and linter.

Commands:

```bash
make format
make lint
```

Rules:

- Line length: 100.
- Use explicit imports.
- Keep imports sorted by Ruff.
- Prefer double quotes only when the formatter chooses them.
- Avoid clever one-liners for workflow code.
- Avoid broad `except Exception` unless the boundary needs to convert unknown failures into a safe user-facing message.
- When catching broad exceptions at an external boundary, log with context and return a safe message.

Docstrings:

- Add docstrings for public modules, protocols, and non-obvious service classes.
- Do not add docstrings that repeat obvious names.
- Prefer clear function names over explanatory comments.

Comments:

- Comments should explain why, not what.
- Use comments for security-sensitive behavior, AI validation gates, and external API quirks.

## Typing

Use mypy strict mode.

Commands:

```bash
make typecheck
```

Rules:

- New functions must have typed parameters and return values.
- Prefer `Protocol` for swappable clients or adapters.
- Prefer `TypedDict` or Pydantic models at external boundaries.
- Use `Any` only at framework edges where third-party generic types are too broad or unstable.
- Keep `# type: ignore[...]` local and specific.
- Every `type: ignore` should have an obvious reason in nearby code or the commit message.

Good:

```python
def should_submit(confidence: float, minimum: float) -> bool:
    return confidence >= minimum
```

Avoid:

```python
def should_submit(confidence, minimum):
    return confidence >= minimum
```

## Runtime Validation

Use Pydantic for untrusted external data:

- AI responses.
- ProgressOS API responses.
- Channel payloads that cross into core services.
- Environment configuration.

Rules:

- AI-facing models must reject unknown keys with `extra="forbid"`.
- Use enums or `Literal` for constrained values.
- Keep nullable fields explicit.
- Validate dates at the boundary.
- Do not pass raw AI dictionaries deep into application code.

Recommended pattern:

```python
model = ParserResponse.model_validate_json(raw_response)
```

Then pass the typed model through the rest of the flow.

## Error Handling

External dependencies can fail:

- Telegram API.
- Groq API.
- ProgressOS API.
- Network.
- Local configuration.

Rules:

- Fail closed for AI and authorization errors.
- Fail safely for write errors.
- Make user-facing errors short and actionable.
- Do not leak stack traces to users.
- Do not leak secrets to logs.
- Preserve useful debug context through correlation IDs.

Error categories to introduce as the project grows:

- `ConfigurationError`
- `AIParseError`
- `LowConfidenceError`
- `UnsupportedIntentError`
- `ProgressOSAPIError`
- `AuthorizationError`
- `ConfirmationExpiredError`

## Logging

Use Python logging through module loggers:

```python
logger = logging.getLogger(__name__)
```

Rules:

- Configure logging once in the application entrypoint.
- Libraries/modules should get loggers, not call `basicConfig`.
- Use parameterized logging for variable data.
- Do not log API keys, bearer tokens, full headers, `.env` values, or raw secrets.
- Be careful with raw user messages. If logged, document the purpose and retention policy.

Good:

```python
logger.info("Submitted ProgressOS action", extra={"action_type": action.type})
```

Avoid:

```python
logger.info(f"Headers: {headers}")
```

## Security

Security boundaries:

- Telegram user input is untrusted.
- Groq output is untrusted.
- ProgressOS API responses are external data.
- Environment variables can be misconfigured.

Required controls:

- Secrets only in `.env`, environment variables, or deployment secret manager.
- Never commit `.env`.
- Never print tokens.
- Validate AI JSON before confirmation.
- Confirm with user before every write.
- ProgressOS validates and authorizes again.
- Use HTTPS for production ProgressOS URLs.
- Use `Idempotency-Key` for retried writes.
- Limit message length before sending to AI.
- Add rate limiting before production use.

Prompt injection rule:

User text must be treated as data. It must never be allowed to override system rules,
JSON schema rules, confirmation rules, or ProgressOS authorization.

## Dependency Management

Rules:

- Keep dependencies in `pyproject.toml`.
- Keep dev-only tools under `[project.optional-dependencies].dev`.
- Prefer established libraries with active maintenance.
- Avoid adding a dependency for small standard-library tasks.
- Review dependency licenses and maintenance before production adoption.
- Use CI to install with `python -m pip install -e ".[dev]"`.

When adding a dependency:

1. Explain why the standard library is not enough.
2. Add the package to `pyproject.toml`.
3. Add tests around the behavior it enables.
4. Run `make check`.

## Testing Strategy

Test pyramid:

- Unit tests for schemas, parser, and mapping logic.
- Integration-style tests for ProgressOS client with mocked HTTP.
- Channel adapter tests with fake Telegram updates.
- End-to-end manual tests for real Telegram and ProgressOS only when secrets are available.

Required test categories:

- Valid AI output.
- Invalid JSON.
- Unknown keys.
- Unsupported intents.
- Low confidence.
- Confirmation accepted.
- Confirmation cancelled.
- ProgressOS success.
- ProgressOS validation error.
- Timeout and retry behavior.
- Secret redaction.

Rules:

- Tests should not call real Groq, Telegram, or ProgressOS by default.
- Use fake clients or mocked HTTP.
- Keep fixtures explicit and readable.
- Test behavior, not implementation details.

## CI Gate

CI runs:

```bash
make check
```

Which runs:

```bash
ruff check .
mypy src
pytest
```

Rules:

- `main` must stay green.
- A failed CI run should be fixed before adding unrelated features.
- If local Python is below 3.11, rely on CI for full validation but still run syntax checks when useful.

Local fallback for syntax checks:

```bash
PYTHONPYCACHEPREFIX=.pycache-local python3 -m compileall src tests
```

## Configuration

Configuration lives in `Settings`.

Rules:

- Environment variable names use uppercase snake case.
- Defaults are allowed only for non-secret safe values.
- Required secrets have no default.
- Production deployments must inject secrets through the platform secret manager.
- Keep `.env.example` complete but fake.

Required variables:

- `TELEGRAM_BOT_TOKEN`
- `GROQ_API_KEY`
- `PROGRESSOS_BASE_URL`
- `PROGRESSOS_API_TOKEN`

## AI Integration

Rules:

- Prompts must request JSON only.
- Parser output must match `docs/AI_CONTRACT.md`.
- Do not accept Markdown or fenced code.
- Do not let the model invent unsupported actions.
- Do not send low-confidence output to confirmation.
- Store enough context later for audit: original message, parser output, user ID, timestamp, and submit result.

When adding a new intent:

1. Update `docs/AI_CONTRACT.md`.
2. Add Pydantic schema.
3. Add parser prompt examples.
4. Add valid and invalid tests.
5. Add ProgressOS mapping.
6. Add confirmation copy.
7. Add docs and changelog notes if user-facing.

## ProgressOS API Integration

Rules:

- Use typed request and response models.
- Use `Accept: application/json`.
- Use bearer auth only from environment.
- Use timeouts on every HTTP call.
- Map errors into safe user-facing messages.
- Do not write directly to the ProgressOS database.
- Do not duplicate Laravel business rules beyond early validation.

Retry rules:

- Retry only idempotent or idempotency-key-protected writes.
- Do not retry validation errors.
- Use bounded retries.
- Surface repeated failures clearly.

## Pull Request Checklist

Before opening or merging a PR:

- Scope is focused.
- Tests are added or updated.
- Docs are updated.
- `make check` passes locally or in CI.
- No secrets are committed.
- AI contract changes include validation changes.
- ProgressOS API changes include contract updates.
- Security impact is considered.
