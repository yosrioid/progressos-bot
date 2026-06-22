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
TELEGRAM_ALLOWED_USER_IDS=123456789
TELEGRAM_REVOKED_USER_IDS=
TELEGRAM_PROGRESSOS_USER_MAP=123456789:77
CONFIRMATION_TTL_SECONDS=900
PENDING_STORE_PATH=./storage/pending.sqlite3
RETRY_QUEUE_PATH=./storage/retry.sqlite3
RETRY_DEAD_LETTER_AFTER_ATTEMPTS=5
LOG_FORMAT=text
```

Run:

```bash
make run
```

Verify:

```bash
make check
```

## Supported Actions

Initial supported intent:

- `create_task`

Planned intents:

- `add_note`
- `update_task`
- `query_status`

Unsupported or ambiguous messages must produce `unsupported`, not a guessed action.

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
- [ProgressOS API research](docs/PROGRESSOS_API_RESEARCH.md)
- [ProgressOS API contract](docs/PROGRESSOS_API_CONTRACT.md)
- [Security notes](docs/SECURITY.md)
- [Roadmap](docs/ROADMAP.md)
