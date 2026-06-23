# ProgressOS Bot

Multi-channel bot gateway for ProgressOS. The first channel adapter is Telegram, but the project should be structured so Discord or other bot channels can be added later without changing the ProgressOS API contract.

The bot accepts natural-language messages, asks Groq to convert them into a strict JSON action payload, validates the payload locally, asks the user for confirmation, then submits the approved action to ProgressOS.

## Current Scope

- Telegram polling bot as the first channel adapter.
- Groq-powered natural-language parser.
- Strict JSON schema with Pydantic validation.
- User confirmation before sending anything to ProgressOS.
- HTTP client for the ProgressOS Laravel API.
- Tests for payload validation and AI response parsing.

## Architecture

```text
Channel user
  -> channel adapter (Telegram first, Discord later)
  -> progressos_bot.ai.parser
  -> Groq chat completion
  -> Pydantic validation
  -> channel confirmation
  -> progressos_bot.progressos_client
  -> ProgressOS Laravel API
```

The bot must not write directly to the ProgressOS database. ProgressOS remains the source of truth and owns all business rules.

## Setup

```bash
cd progressos-bot
python -m venv .venv
source .venv/bin/activate
make install
cp .env.example .env
```

Fill `.env`:

```env
TELEGRAM_BOT_TOKEN=...
GROQ_API_KEY=...
PROGRESSOS_BASE_URL=http://127.0.0.1:8000
PROGRESSOS_API_TOKEN=...
PROGRESSOS_API_VERSION=v1
TELEGRAM_ALLOWED_USER_IDS=123456789
TELEGRAM_REVOKED_USER_IDS=
TELEGRAM_PROGRESSOS_USER_MAP=123456789:77
CONFIRMATION_TTL_SECONDS=900
PENDING_STORE_PATH=./storage/pending.sqlite3
RETRY_QUEUE_PATH=./storage/retry.sqlite3
RETRY_DEAD_LETTER_AFTER_ATTEMPTS=5
CAPTURE_ENABLED_INTENTS=create_task,create_blocker,log_work,log_daily_progress,capture_learning
CAPTURE_MAX_INPUT_CHARS=2000
APP_TIMEZONE=Asia/Jakarta
APP_DEFAULT_LANGUAGE=id
LOG_FORMAT=text
```

Run:

```bash
make run
```

Local development uses Telegram polling by default. For webhook deployment, set:

```env
TELEGRAM_RUN_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://example.com/telegram/webhook
TELEGRAM_WEBHOOK_PATH=/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=change-me
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8080
HEALTH_PATH=/health
READINESS_PATH=/ready
```

Webhook mode exposes `HEALTH_PATH` and `READINESS_PATH` without secrets or debug data.
When `TELEGRAM_WEBHOOK_URL` is set, startup registers that URL with Telegram and sends
`TELEGRAM_WEBHOOK_SECRET` as Telegram's webhook secret token.

Verify:

```bash
make check
```

## Supported Actions

Supported capture intents:

- `create_task`
- `create_blocker`
- `log_work`
- `log_daily_progress`
- `capture_learning`
- `unsupported`

Unsupported or ambiguous messages must produce `unsupported`, not a guessed action.
Relative dates such as "today" or "besok" are resolved from `APP_TIMEZONE`, which defaults
to `Asia/Jakarta`.
Parser language `unknown` is normalized to `APP_DEFAULT_LANGUAGE`, which defaults to `id`.
Capture intents can be limited with `CAPTURE_ENABLED_INTENTS`; disabled intents are rejected
before confirmation and are not sent to ProgressOS.
Very long capture messages are rejected before parser calls using `CAPTURE_MAX_INPUT_CHARS`.
ProgressOS requests include `X-ProgressOS-API-Version` from `PROGRESSOS_API_VERSION`,
defaulting to `v1`.

## Safety Rules

- Never send AI output to ProgressOS without local schema validation.
- Never submit an action before explicit Telegram user confirmation.
- Never trust Groq confidence alone; validate required fields and allowed enum values.
- Never allow unknown fields in AI payloads.
- Never let the Telegram bot bypass Laravel authorization or business logic.
- Store enough audit context in ProgressOS later: original message, parsed payload, user ID, timestamp, and submit result.

## Project Docs

- [Bot rules](docs/RULES.md)
- [AI contract](docs/AI_CONTRACT.md)
- [Product phases](docs/PHASES.md)
- [Python engineering guide](docs/PYTHON_ENGINEERING_GUIDE.md)
- [Deployment notes](docs/DEPLOYMENT.md)
- [ProgressOS API research](docs/PROGRESSOS_API_RESEARCH.md)
- [ProgressOS API contract](docs/PROGRESSOS_API_CONTRACT.md)
- [Security notes](docs/SECURITY.md)
- [Roadmap](docs/ROADMAP.md)
