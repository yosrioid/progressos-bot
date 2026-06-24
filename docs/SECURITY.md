# Security Notes

## Secrets

Keep these values only in `.env` or the deployment secret manager:

- `TELEGRAM_BOT_TOKEN`
- `GROQ_API_KEY`
- `PROGRESSOS_API_TOKEN`

Never commit `.env`.

## Secret Rotation Runbook

Rotate secrets from the provider first, then update the deployment secret store, then
restart the bot. Do not paste old or new secret values into tickets, chat, logs, or pull
requests.

Use this order for planned rotation:

1. Create the replacement secret in Telegram, Groq, or ProgressOS.
2. Store the replacement value in the deployment secret manager.
3. Restart the bot process so it reads the new environment.
4. Run a minimal smoke check:
   - `/version` returns the expected app version.
   - `/diagnostics` shows the expected environment, run mode, and configured flags.
   - A safe capture draft reaches confirmation but is not submitted unless explicitly
     confirmed.
5. Revoke the previous secret after the new deployment is healthy.
6. Watch logs for Telegram, Groq, ProgressOS, and webhook authentication errors.

For suspected compromise, revoke the old secret before redeploying. Cancel active pending
drafts if an operator believes a compromised channel or model key could have influenced
pending confirmations. Keep retry queue data only when the queued payloads were created
under a trusted token and still match the intended ProgressOS user attribution.

Recommended rotation triggers:

- A secret was committed, pasted into chat, exposed in logs, or shared outside the
  deployment boundary.
- A team member or automation with secret access is offboarded.
- Provider audit logs show unexpected usage.
- Deployment hosts, CI secrets, or runtime secret stores were rebuilt after an incident.
- Periodic production hygiene requires scheduled rotation.

## Model Key Scope

`GROQ_API_KEY` is used only for parsing natural-language capture text into the strict local
action schema. The key should not have access to unrelated provider projects, training
datasets, production administration, billing administration, or non-bot workloads.

Operational guidance:

- Use a dedicated provider key for this bot and environment.
- Prefer separate keys for local, staging, and production.
- Restrict the key to the minimum model/API access the deployment needs when the provider
  supports scoped keys.
- Keep `GROQ_MODEL` and `GROQ_STRUCTURED_OUTPUT_MODE` as configuration changes, not code
  hotfixes, and evaluate model changes before changing production defaults.
- Treat model output as untrusted even when using a scoped key or structured outputs.
- Never reuse the Groq key as a ProgressOS, Telegram, webhook, CI, or database secret.

## Authorization

The first version uses a single ProgressOS API token. Before production use, ProgressOS
should map channel user IDs to ProgressOS users and enforce permissions server-side. That
server-side mapping depends on a ProgressOS-owned identity resolution contract that is not
available to the bot yet.

Telegram access is bootstrapped with `TELEGRAM_ALLOWED_USER_IDS`, a comma-separated list
of stable Telegram user IDs. An empty allowlist rejects all Telegram users. Display names
are never trusted for authorization.

Access revocation is bootstrapped with `TELEGRAM_REVOKED_USER_IDS`, a comma-separated list
of stable Telegram user IDs. Revoked IDs are rejected even when they still appear in the
allowlist.

Telegram-to-ProgressOS attribution is bootstrapped with `TELEGRAM_PROGRESSOS_USER_MAP`.
Use comma-separated `telegram_user_id:progressos_user_id` pairs. The bot rejects read
commands and confirmed write actions when the Telegram user is not mapped.
This bootstrap mapping should be removed once ProgressOS exposes server-side identity
resolution for channel users.

Confirmed writes include audit notes with stable source IDs, mapped ProgressOS user ID,
parser summary, submit timestamp, and idempotency key. Audit notes must not include bearer
tokens, raw request headers, or `.env` values.

Pending confirmation drafts expire after `CONFIRMATION_TTL_SECONDS`. Expired drafts are
dropped instead of being submitted to ProgressOS.

When `PENDING_STORE_PATH` is configured, pending drafts are stored in a local SQLite file
so confirmation callbacks can survive bot restarts. Treat that file as runtime data and do
not commit it.

When `RETRY_QUEUE_PATH` is configured, exhausted transient writes are stored in a local
SQLite queue with the quick-capture payload and original idempotency key. The queue must
not store bearer tokens or raw request headers.

Queued retry submissions are moved to dead-letter storage after
`RETRY_DEAD_LETTER_AFTER_ATTEMPTS` so repeated failures remain visible without retrying
forever.

`LOG_FORMAT=json` emits machine-readable operational logs with timestamp, level, logger,
message, and exception text. Logs must still avoid bearer tokens, raw request headers, and
`.env` values.

Webhook mode verifies `X-Telegram-Bot-Api-Secret-Token` when
`TELEGRAM_WEBHOOK_SECRET` is configured. Keep that secret in `.env` or deployment secret
storage. Health and readiness responses only expose coarse status strings and must not
include tokens, headers, environment values, or debug payloads.

## AI Safety Boundary

AI output is a draft, not an instruction. The bot validates the shape and asks for confirmation, then ProgressOS validates business rules again.

`CAPTURE_PRE_PARSER_GUARD_MODE=basic` enables an optional pre-parser guard for high-risk
deployments. It blocks obvious prompt-injection, system-prompt exfiltration, and
secret-exfiltration text before the message is sent to the model. Keep local schema
validation, explicit confirmation, ProgressOS authorization, and secret redaction enabled;
the guard is only an early filter.

## Logging

Logs may include normal error messages, but must not include API keys or bearer tokens. Be careful when logging HTTP request headers or full exception objects from external clients.
