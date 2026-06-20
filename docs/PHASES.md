# Product Phases

This document is the detailed execution plan for ProgressOS Bot. It defines feature phases,
scope boundaries, acceptance criteria, and verification gates.

ProgressOS Bot is a multi-channel gateway. Telegram is the first channel adapter, but the
core contracts must stay channel-neutral.

## Phase Rules

Every phase must follow these rules:

1. Keep ProgressOS Laravel as the source of truth.
2. Keep AI output as a draft until local validation and user confirmation pass.
3. Add or update tests for every new parser, schema, API, or channel behavior.
4. Update `docs/AI_CONTRACT.md` when AI input or output changes.
5. Update `docs/PROGRESSOS_API_CONTRACT.md` when the Laravel API contract changes.
6. Run `make check` before merging when Python 3.11 and dev dependencies are available.
7. Do not add a new channel by copying business logic from another channel.
8. Prefer small, shippable slices over broad rewrites.

## Phase 0: Repository Foundation

Status: complete.

Goal: create a maintainable Python 3.11+ project foundation with strict governance.

Features:

- `src/` package layout.
- `pyproject.toml` package metadata.
- `Makefile` developer commands.
- `.env.example` for required configuration.
- GitHub Actions CI on `main` and pull requests.
- Bot governance docs:
  - `AGENTS.md`
  - `CONTRIBUTING.md`
  - `docs/RULES.md`
  - `docs/AI_CONTRACT.md`
  - `docs/SECURITY.md`
  - `docs/PROGRESSOS_API_CONTRACT.md`
  - `docs/PROGRESSOS_API_RESEARCH.md`

Acceptance criteria:

- `make check` passes in CI.
- No secrets or local env files are committed.
- Project name is `progressos-bot`.
- Import package remains `progressos_bot`.

## Phase 1: Telegram Capture MVP

Status: in progress.

Goal: let a Telegram user submit a natural-language capture request, review the parsed
payload, and confirm before the bot sends it to ProgressOS.

Features:

- Telegram polling adapter.
- `/start` command.
- `/cancel` command.
- Free-form text handler.
- Groq parser client.
- AI parser prompt for JSON-only output.
- Strict Pydantic schemas for AI parser output.
- Minimum confidence gate through `AI_MIN_CONFIDENCE`.
- In-memory pending action store.
- Telegram inline confirmation buttons.
- Confirmed write to ProgressOS.
- Cancel flow that discards pending action.

Supported intents:

- `create_task`
- `unsupported`

Acceptance criteria:

- Bot never sends unvalidated AI output to ProgressOS.
- Bot never sends an action before explicit user confirmation.
- Invalid JSON is rejected.
- Unknown JSON keys are rejected.
- Unsupported or ambiguous messages do not become guessed tasks.
- Tests cover valid task parsing, invalid parser output, and unsupported output.

Verification:

```bash
make check
```

Manual verification:

1. Send a valid task message.
2. Confirm the action.
3. Confirm ProgressOS receives one request.
4. Send an ambiguous message.
5. Confirm the bot rejects or marks it unsupported.
6. Send `/cancel`.
7. Confirm pending action is removed.

## Phase 2: ProgressOS Quick Capture Completion

Status: in progress.

Goal: complete the full quick-capture contract against `POST /api/v1/quick-capture`.

Features:

- Local request schema for quick capture.
- Idempotency key generation for write requests.
- Safe retry behavior for transient HTTP failures.
- Response handling for:
  - `message`
  - `record`
  - `record_path`
  - validation errors
- Clear user-facing error messages.
- Mapping from AI intent payloads to ProgressOS quick-capture payloads.

Supported quick-capture types:

- `task`
- `blocker`
- `work_log`
- `daily_progress`
- `learning`

Required implementation rules:

- Use `Idempotency-Key` for retried writes.
- Keep ProgressOS validation as the final business-rule gate.
- Do not expose raw HTTP headers or bearer tokens in logs.
- Tests must mock HTTP responses and failure cases.

Acceptance criteria:

- Duplicate retry does not create duplicate records when Laravel honors idempotency.
- Validation errors from Laravel are displayed without leaking request secrets.
- Network timeout produces a safe user-facing failure.
- Response message or record path is shown after successful capture.

Tests to add:

- Successful quick capture.
- Validation error response.
- Timeout/retry path.
- Idempotency key is included.
- Response with missing optional fields remains safe.

Current implementation slice:

- `create_task` maps to quick-capture `task`.
- The client adds `Idempotency-Key` to every confirmed submit.
- The client retries timeout, network, and 5xx failures with the same idempotency key.
- Laravel `422` validation responses are parsed into a typed validation error.
- Telegram shows safe validation/transient/client error messages.

## Phase 3: Expanded Capture Intents

Status: planned.

Goal: support ProgressOS capture types beyond task creation while keeping AI schemas strict.

Features:

- `create_blocker`
- `log_work`
- `log_daily_progress`
- `capture_learning`
- Shared capture mapper.
- Intent-specific confirmation text.
- Intent-specific test fixtures in Indonesian and English.

AI contract additions:

- New allowed `intent` values.
- Payload schema per intent.
- Examples of supported and rejected messages.
- Explicit unsupported examples for out-of-scope requests.

Acceptance criteria:

- Each intent has its own Pydantic schema.
- Cross-intent payload fields are rejected.
- AI prompt examples cover every supported intent.
- Tests include low-confidence and malformed payload cases.

Suggested implementation order:

1. `create_blocker`
2. `log_work`
3. `log_daily_progress`
4. `capture_learning`

## Phase 4: Read-Only Commands

Status: planned.

Goal: let users ask ProgressOS for read-only status summaries without changing data.

Commands:

- `/standup`
- `/dashboard`
- `/search <query>`
- `/overdue`
- `/kanban`
- `/learning_stats`

Rules:

- Read commands must call read-only ProgressOS API endpoints.
- Read command responses should be concise and channel-friendly.
- Read commands must respect ProgressOS authorization.
- Search queries must be length-limited.
- Do not send read results back into the AI model unless the feature explicitly needs it.

Acceptance criteria:

- Each command has a typed request/response boundary.
- Empty states are handled cleanly.
- Unauthorized responses are handled without leaking details.
- Tests cover success, empty, unauthorized, and server error responses.

## Phase 5: User Identity And Authorization

Status: planned.

Goal: move from one shared ProgressOS API token to per-user authorization.

Features:

- Channel user identity model.
- Mapping from Telegram user ID to ProgressOS user ID.
- Authorization check before showing or submitting actions.
- Admin-only allowlist bootstrap.
- Revocation flow.
- Audit metadata on submitted actions.

Security requirements:

- Never trust channel display names as identity.
- Use stable channel IDs.
- Keep mapping server-side where possible.
- ProgressOS must enforce final permission checks.
- Logs must not include raw auth tokens.

Acceptance criteria:

- Unknown Telegram user cannot submit actions.
- Revoked user cannot submit actions.
- Authorized user actions are attributed to the correct ProgressOS user.
- Tests cover allowed, unknown, revoked, and malformed identity states.

## Phase 6: Persistence And Operational Reliability

Status: planned.

Goal: make pending confirmations and delivery behavior survive bot restarts.

Features:

- Persistent pending action store.
- Confirmation expiry.
- Rehydration after restart.
- Idempotency-aware retry queue.
- Dead-letter handling for repeated failures.
- Structured operational logs.

Recommended storage:

- SQLite for single-instance local deployments.
- PostgreSQL or ProgressOS-owned storage for production.

Acceptance criteria:

- Pending confirmation survives restart.
- Expired confirmation cannot be submitted.
- Repeated HTTP failures are visible to operators.
- Retry behavior does not create duplicate ProgressOS records.

## Phase 7: Webhook Deployment

Status: planned.

Goal: support production deployment through webhooks instead of polling.

Features:

- Webhook server entrypoint.
- Health endpoint.
- Readiness endpoint.
- Graceful shutdown.
- Deployment config examples.
- Reverse proxy notes.
- Telegram webhook secret verification where supported.

Rules:

- Polling remains useful for local development.
- Webhook mode is required for production environments with controlled ingress.
- Do not expose debug endpoints publicly.

Acceptance criteria:

- Webhook mode can receive updates.
- Polling mode still works locally.
- Health check does not reveal secrets.
- Deployment docs include required env variables.

## Phase 8: Multi-Channel Core

Status: planned.

Goal: add new channel adapters without duplicating parser, validation, or ProgressOS client
logic.

Candidate channels:

- Discord
- Slack
- Web chat
- CLI for admin testing

Required abstractions:

- `ChannelMessage`
- `ChannelUser`
- `ConfirmationRequest`
- `ConfirmationDecision`
- `ChannelAdapter`

Rules:

- Channel adapters translate channel events into core commands.
- Core services own parsing, validation, confirmation state, and ProgressOS submission.
- Channel adapters own only channel-specific formatting and transport.

Acceptance criteria:

- Telegram behavior still passes after extracting core abstractions.
- At least one non-Telegram adapter can reuse the same core flow.
- Tests cover core flow without Telegram-specific classes.

## Phase 9: Observability And Admin Tools

Status: planned.

Goal: make the bot easy to operate and debug safely.

Features:

- Structured JSON logging.
- Request correlation IDs.
- Metrics for parse success, confirmation rate, submit success, and submit failure.
- Admin command for version/build info.
- Safe diagnostic command for configuration status.
- Error reporting integration.

Security rules:

- Diagnostic output must not include secrets.
- Logs must redact bearer tokens and API keys.
- Raw user messages should be logged only when explicitly allowed and documented.

Acceptance criteria:

- Operators can identify failing dependency: Telegram, Groq, or ProgressOS.
- A failed action can be traced by correlation ID.
- Secret redaction has tests.

## Phase 10: Product Hardening

Status: planned.

Goal: make the system dependable for real daily use.

Features:

- Rate limiting.
- Abuse prevention.
- Prompt injection test cases.
- Language normalization for Indonesian and English.
- Better date parsing with timezone awareness.
- User preference defaults.
- Admin-managed feature flags.
- Backward-compatible API versioning.

Acceptance criteria:

- High-volume user cannot exhaust bot resources.
- Prompt injection attempts cannot bypass validation or confirmation.
- Date interpretation is deterministic for `Asia/Jakarta` unless configured otherwise.
- Feature flags can disable risky intents without redeploying.

## Definition Of Done

A feature is done only when:

- Code is implemented.
- Tests cover success and failure behavior.
- Docs are updated.
- Security impact is reviewed.
- `make check` passes in CI.
- User-facing messages are clear in Indonesian.
- ProgressOS remains the source of truth.
