# ProgressOS API Contract

This is the current Laravel endpoint contract for ProgressOS bot integrations.

## Endpoint

```http
POST /api/v1/quick-capture
```

## Headers

```http
Authorization: Bearer <PROGRESSOS_API_TOKEN>
Content-Type: application/json
Accept: application/json
Idempotency-Key: <unique-key-per-confirmed-submit>
```

## Request Body

```json
{
  "type": "task",
  "title": "Follow up invoice client A",
  "project_name": "ProgressOS",
  "notes": "User asked from Telegram: buat task follow up invoice client A besok prioritas high",
  "date": "2026-06-20"
}
```

Allowed `type` values:

- `task`
- `blocker`
- `work_log`
- `daily_progress`
- `learning`

Optional fields:

- `date`
- `notes`
- `project_name`
- `duration_minutes`

Use `Idempotency-Key` for retries.

## Current Bot Mapping

The Telegram flow stores a confirmed `ProgressOSActionRequest` internally, then maps it to
the quick-capture payload before calling Laravel.

Current supported mapping:

- `create_task` -> `type: "task"`
- `payload.title` -> `title`
- `payload.due_date` -> `date`
- `original_text`, source channel, source user, source chat, and optional description -> `notes`
- `create_blocker` -> `type: "blocker"`
- `payload.severity` -> `notes`
- `log_work` -> `type: "work_log"`
- `payload.duration_minutes` -> `duration_minutes`
- `payload.project_name` -> `project_name`
- `payload.date` -> `date`
- `log_daily_progress` -> `type: "daily_progress"`
- `log_daily_progress.payload.project_name` -> `project_name`
- `log_daily_progress.payload.date` -> `date`
- `capture_learning` -> `type: "learning"`
- `capture_learning.payload.project_name` -> `project_name`
- `capture_learning.payload.date` -> `date`

Unsupported actions are not submitted.

## Expected Success Response

```json
{
  "data": {
    "id": 42,
    "title": "Follow up invoice client A"
  },
  "record": {
    "id": 42,
    "title": "Follow up invoice client A"
  },
  "record_path": "/tasks/42",
  "message": "Captured."
}
```

## Expected Error Response

```json
{
  "message": "Validation failed",
  "errors": {
    "title": ["The title field is required."]
  }
}
```

The bot treats `422` responses as validation errors and shows the response `message` to the
user without exposing request headers, bearer tokens, or raw exception traces.

## Read-Only Standup

```http
GET /api/v1/standup
Authorization: Bearer <PROGRESSOS_API_TOKEN>
Accept: application/json
```

The bot formats a concise Telegram response from `items` or a list-shaped `data` field.
Empty responses show `Tidak ada item standup.`. Unauthorized responses are handled with a
safe generic message without exposing raw server details.

## Read-Only Dashboard

```http
GET /api/v1/dashboard
Authorization: Bearer <PROGRESSOS_API_TOKEN>
Accept: application/json
```

The bot formats a concise Telegram response from `metrics`, `items`, or a list-shaped
`data` field. Empty responses show `Tidak ada ringkasan dashboard.`. Unauthorized
responses are handled with a safe generic message without exposing raw server details.

## Read-Only Search

```http
GET /api/v1/search?q=<query>
Authorization: Bearer <PROGRESSOS_API_TOKEN>
Accept: application/json
```

Telegram `/search` requires a non-empty query and rejects queries longer than 120
characters before calling ProgressOS. The bot formats results from `results`, `items`, or
a list-shaped `data` field. Empty responses show `Tidak ada hasil pencarian.`.
