# Deployment Notes

ProgressOS Bot supports local polling and production webhook mode. Keep polling for local
development, and use webhook mode only behind controlled ingress.

## Required Environment

```env
TELEGRAM_BOT_TOKEN=...
GROQ_API_KEY=...
PROGRESSOS_BASE_URL=https://progressos.example.com
PROGRESSOS_API_TOKEN=...
TELEGRAM_ALLOWED_USER_IDS=123456789
TELEGRAM_PROGRESSOS_USER_MAP=123456789:77
TELEGRAM_RUN_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://bot.example.com/telegram/webhook
TELEGRAM_WEBHOOK_PATH=/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=change-me
WEBHOOK_HOST=127.0.0.1
WEBHOOK_PORT=8080
HEALTH_PATH=/health
READINESS_PATH=/ready
LOG_FORMAT=json
```

Use deployment secret storage for tokens and webhook secret values. Do not bake them into
images, service files, or reverse proxy config.

For rotation and incident response, follow the secret rotation and model-key scope
guidance in `docs/SECURITY.md`.

## Process Command

Run the package entrypoint in webhook mode:

```bash
progressos-bot
```

or:

```bash
python -m progressos_bot.main
```

The process handles `SIGINT` and `SIGTERM` by stopping the HTTP listener and shutting down
the Telegram application lifecycle. Supervisors should send `SIGTERM` first and allow a
short grace period before force-killing the process.

## Health Checks

Use:

```text
GET /health
GET /ready
```

`/health` confirms the HTTP listener is alive. `/ready` confirms the Telegram application
has started. Both responses return only coarse status values and never include secrets.

## Retry Queue Operations

When `RETRY_QUEUE_PATH` is configured, operators can inspect retry storage without opening
SQLite manually:

```bash
progressos-bot-retry-queue --path "$RETRY_QUEUE_PATH" status
progressos-bot-retry-queue --path "$RETRY_QUEUE_PATH" dead-letters
progressos-bot-retry-queue --path "$RETRY_QUEUE_PATH" diagnostic-bundle \
  --correlation-id "$CORRELATION_ID"
```

Both commands print JSON. Dead-letter output is metadata-only: idempotency key, capture
type, redacted title, timestamps, attempt count, and redacted last error. It does not print
the full quick-capture payload, request headers, bearer tokens, or environment values.

Add `--idempotency-key "$IDEMPOTENCY_KEY"` to `diagnostic-bundle` when the incident also
has a retry or dead-letter entry. Retry storage does not persist correlation IDs, so the
bundle includes queue matches only when the idempotency key is provided.

After confirming the exact idempotency key from `dead-letters`, operators can move one
entry back to the retry queue or discard it:

```bash
progressos-bot-retry-queue --path "$RETRY_QUEUE_PATH" requeue \
  --idempotency-key "$IDEMPOTENCY_KEY" \
  --confirm "$IDEMPOTENCY_KEY"

progressos-bot-retry-queue --path "$RETRY_QUEUE_PATH" discard \
  --idempotency-key "$IDEMPOTENCY_KEY" \
  --confirm "$IDEMPOTENCY_KEY"
```

`requeue` preserves the original idempotency key. Both mutation commands fail before
touching the dead-letter entry unless `--confirm` exactly matches `--idempotency-key`.

## Production Recovery Runbook

For webhook incidents:

1. Check `GET /health` and `GET /ready` from the deployment network.
2. Confirm the Telegram webhook secret configured in deployment matches Telegram webhook
   setup. Do not print or paste the secret into logs.
3. Search JSON logs for the user-visible correlation ID.
4. Export a redacted bundle:

   ```bash
   progressos-bot-retry-queue --path "$RETRY_QUEUE_PATH" diagnostic-bundle \
     --correlation-id "$CORRELATION_ID"
   ```

For dependency outages:

1. Use logs and error reporter output to identify whether the failing dependency is Groq,
   Telegram, ProgressOS, or local SQLite storage.
2. Check retry queue counts with `status`.
3. Inspect dead-letter metadata with `dead-letters`; use the idempotency key to export a
   focused diagnostic bundle when needed.
4. After a transient ProgressOS outage is resolved, use `requeue` for entries that should
   be submitted again. The original idempotency key is preserved.
5. Use `discard` only for entries that are invalid, obsolete, or already resolved
   elsewhere.
6. If any log, bundle, or operator terminal includes a real secret, rotate that secret
   following `docs/SECURITY.md`.

## Reverse Proxy

Terminate TLS at the reverse proxy, then forward only the configured webhook path to the
bot listener:

```nginx
location = /telegram/webhook {
    proxy_pass http://127.0.0.1:8080/telegram/webhook;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

Keep health and readiness endpoints private to the platform or internal network. Do not
publish debug endpoints. The bot validates Telegram's
`X-Telegram-Bot-Api-Secret-Token` header when `TELEGRAM_WEBHOOK_SECRET` is configured.
