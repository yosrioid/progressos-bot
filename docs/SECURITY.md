# Security Notes

## Secrets

Keep these values only in `.env` or the deployment secret manager:

- `TELEGRAM_BOT_TOKEN`
- `GROQ_API_KEY`
- `PROGRESSOS_API_TOKEN`

Never commit `.env`.

## Authorization

The first version uses a single ProgressOS API token. Before production use, ProgressOS should map channel user IDs to ProgressOS users and enforce permissions server-side.

Telegram access is bootstrapped with `TELEGRAM_ALLOWED_USER_IDS`, a comma-separated list
of stable Telegram user IDs. An empty allowlist rejects all Telegram users. Display names
are never trusted for authorization.

## AI Safety Boundary

AI output is a draft, not an instruction. The bot validates the shape and asks for confirmation, then ProgressOS validates business rules again.

## Logging

Logs may include normal error messages, but must not include API keys or bearer tokens. Be careful when logging HTTP request headers or full exception objects from external clients.
