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
