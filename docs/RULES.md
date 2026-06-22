# Bot Rules

## Non-Negotiable Rules

1. Telegram is only the first input channel. ProgressOS owns business rules and persistence.
2. Groq output is untrusted until it passes local Pydantic validation.
3. The bot must ask for user confirmation before calling ProgressOS.
4. AI responses must be JSON only. Markdown, prose, explanations, and code fences are invalid.
5. Unknown JSON keys are invalid.
6. Unsupported intents must use `unsupported`; the model must not invent actions.
7. Low-confidence parses must not be submitted.
8. API tokens must come from environment variables only.
9. Logs must not expose Telegram tokens, Groq API keys, or ProgressOS API tokens.

## Strict AI Response Format

Groq must return exactly one JSON object:

```json
{
  "intent": "create_task",
  "confidence": 0.88,
  "language": "id",
  "payload": {
    "title": "Follow up invoice client A",
    "description": "User asked from Telegram",
    "due_date": "2026-06-21",
    "priority": "high"
  },
  "user_confirmation_text": "Buat task \"Follow up invoice client A\" dengan prioritas high untuk 2026-06-21?"
}
```

Allowed `intent` values:

- `create_task`
- `create_blocker`
- `log_work`
- `log_daily_progress`
- `capture_learning`
- `unsupported`

Allowed `priority` values:

- `low`
- `medium`
- `high`
- `urgent`

Date format:

- `YYYY-MM-DD`
- `null` if not provided

## Rejection Rules

Reject the AI result when:

- JSON cannot be parsed.
- `intent` is unknown.
- `confidence` is below `AI_MIN_CONFIDENCE`.
- Required payload fields are missing.
- Payload includes unknown keys.
- The confirmation text is empty.

## Channel Conversation Rules

1. User sends free-form message.
2. Bot parses message with Groq.
3. Bot shows the normalized action to the user.
4. User taps `Confirm` or `Cancel`.
5. Only `Confirm` can call ProgressOS.
6. `Cancel` discards the pending action.
7. Telegram users must be allowed and not revoked by stable Telegram user ID before parser, read, or write flows run.
8. Read commands require a Telegram-to-ProgressOS user mapping.
9. Confirmed writes require a Telegram-to-ProgressOS user mapping.
10. Confirmed writes must include source identity, parser summary, submit timestamp, and idempotency key in audit notes.

## ProgressOS Integration Rules

For quick capture writes, the bot should call:

```http
POST /api/v1/quick-capture
Authorization: Bearer <PROGRESSOS_API_TOKEN>
Content-Type: application/json
```

Laravel should validate the action again. Python-side validation is only the first gate.
