# Roadmap

## Phase 1: Bot Foundation

- Telegram polling bot.
- Groq parser.
- Strict Pydantic action schema.
- Confirmation flow.
- Tests for parser and schema behavior.

## Phase 2: ProgressOS Quick Capture Integration

- Use Laravel endpoint `POST /api/v1/quick-capture`.
- Add `Idempotency-Key` for safe retries.
- Support `task`, `blocker`, `work_log`, `daily_progress`, and `learning`.
- Parse AI output into locally validated quick capture payloads.
- Handle ProgressOS response fields: `message`, `record`, and `record_path`.

## Phase 3: Read Commands

- `/standup`
- `/dashboard`
- `/search <query>`
- `/overdue`
- `/kanban`
- `/learning_stats`

## Phase 4: More Write Actions

- Update task status.
- Log/unlog habit.
- Mark notifications read.
- Create report snapshot.

Each new intent must add:

- Pydantic payload schema.
- Prompt contract update.
- Validation tests.
- ProgressOS API contract or research update.
- Local payload validation.

## Phase 5: Multi-Channel And Production Hardening

- Discord adapter.
- Webhook mode instead of polling.
- Per-user authorization mapping between channel users and ProgressOS users.
- Rate limits.
- Structured JSON logging.
- Error reporting.
- Persistent pending actions instead of in-memory drafts.
