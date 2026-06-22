# AI Contract

This file defines the contract between channel text input, Groq parsing, and the local validator. Telegram is the first channel adapter.

## Model Responsibility

The model only converts natural language into a candidate action. It does not decide whether the action is allowed in ProgressOS.

## Parser Input

```json
{
  "current_date": "2026-06-19",
  "channel_message": "buat task follow up invoice client A besok prioritas high"
}
```

## Parser Output

The parser must return one JSON object and nothing else:

```json
{
  "intent": "create_task",
  "confidence": 0.91,
  "language": "id",
  "payload": {
    "title": "Follow up invoice client A",
    "description": null,
    "due_date": "2026-06-20",
    "priority": "high"
  },
  "user_confirmation_text": "Buat task \"Follow up invoice client A\" untuk 2026-06-20 dengan prioritas high?"
}
```

## Supported Intent: create_task

Required payload fields:

- `title`
- `priority`

Optional payload fields:

- `description`
- `due_date`

## Supported Intent: create_blocker

Use this when the user wants to capture a blocker or impediment that should be stored in
ProgressOS quick capture.

Required payload fields:

- `title`
- `severity`

Optional payload fields:

- `description`

Example:

```json
{
  "intent": "create_blocker",
  "confidence": 0.89,
  "language": "id",
  "payload": {
    "title": "Blocked by missing API token",
    "description": "Need ProgressOS token from admin",
    "severity": "high"
  },
  "user_confirmation_text": "Catat blocker \"Blocked by missing API token\" dengan severity high?"
}
```

## Supported Intent: unsupported

Use this for unsupported commands, ambiguous messages, or messages that cannot be safely converted.

```json
{
  "intent": "unsupported",
  "confidence": 0.8,
  "language": "id",
  "payload": {
    "reason": "Message asks for a status query, but query_status is not enabled yet."
  },
  "user_confirmation_text": "Perintah ini belum didukung."
}
```

## Local Validation Gates

The bot rejects the response before user confirmation when:

- The response is not valid JSON.
- The response has unknown top-level fields.
- The payload has unknown fields.
- The intent and payload shape do not match.
- The confidence is below `AI_MIN_CONFIDENCE`.
- The confirmation text is missing.
