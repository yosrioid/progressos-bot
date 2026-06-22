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
