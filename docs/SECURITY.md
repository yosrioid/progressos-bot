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

Access revocation is bootstrapped with `TELEGRAM_REVOKED_USER_IDS`, a comma-separated list
of stable Telegram user IDs. Revoked IDs are rejected even when they still appear in the
allowlist.

Telegram-to-ProgressOS attribution is bootstrapped with `TELEGRAM_PROGRESSOS_USER_MAP`.
Use comma-separated `telegram_user_id:progressos_user_id` pairs. The bot rejects read
commands and confirmed write actions when the Telegram user is not mapped.

Confirmed writes include audit notes with stable source IDs, mapped ProgressOS user ID,
parser summary, submit timestamp, and idempotency key. Audit notes must not include bearer
tokens, raw request headers, or `.env` values.

Pending confirmation drafts expire after `CONFIRMATION_TTL_SECONDS`. Expired drafts are
dropped instead of being submitted to ProgressOS.

When `PENDING_STORE_PATH` is configured, pending drafts are stored in a local SQLite file
so confirmation callbacks can survive bot restarts. Treat that file as runtime data and do
not commit it.

## AI Safety Boundary

AI output is a draft, not an instruction. The bot validates the shape and asks for confirmation, then ProgressOS validates business rules again.

## Logging

Logs may include normal error messages, but must not include API keys or bearer tokens. Be careful when logging HTTP request headers or full exception objects from external clients.
