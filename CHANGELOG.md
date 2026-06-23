# Changelog

All notable changes to ProgressOS Bot are documented in this file.

## v0.1.0 - 2026-06-23

Initial release of ProgressOS Bot.

### Added

- Telegram polling and webhook channel adapters.
- Strict Groq-powered natural-language parser for capture intents.
- Local Pydantic validation for AI parser output with unknown-field rejection.
- Explicit user confirmation before sending capture writes to ProgressOS.
- ProgressOS quick-capture integration through `POST /api/v1/quick-capture`.
- Idempotency keys and safe transient retry behavior for confirmed writes.
- Supported capture intents:
  - `create_task`
  - `create_blocker`
  - `log_work`
  - `log_daily_progress`
  - `capture_learning`
  - `unsupported`
- Read-only ProgressOS commands:
  - `/standup`
  - `/dashboard`
  - `/search`
  - `/overdue`
  - `/kanban`
  - `/learning_stats`
- Telegram allowlist, revoked-user checks, and local user mapping.
- Persistent pending draft store and retry queue.
- Webhook health and readiness endpoints.
- Basic metrics, admin commands, and `/version` command.
- API version header support through `PROGRESSOS_API_VERSION`.

### Security

- AI output is validated locally and remains a draft until user confirmation.
- ProgressOS remains the source of truth for writes and business rules.
- Secrets, bearer tokens, and raw HTTP credentials are kept out of logs and user-facing errors.

### Verification

- GitHub Actions CI runs `make check` on Python 3.11.
- Product phases 0-9 are complete.
- Phase 10 is complete for bot-owned scope.
