# ProgressOS API Research

Tanggal audit: 2026-06-20

## Ringkasan

Laravel ProgressOS sudah menyediakan REST API matang untuk integrasi bot dan automation. Endpoint paling relevan untuk project ini adalah `POST /api/v1/quick-capture`, bukan kontrak draft lama `POST /api/assistant/actions`.

Project bot ini sebaiknya diposisikan sebagai gateway multi-channel untuk ProgressOS. Telegram adalah adapter pertama, tetapi desain berikutnya harus bisa menampung Discord atau channel bot lain tanpa mengubah kontrak inti parser dan ProgressOS client.

## Sumber Yang Dicek

- `/Users/oirsoy/Downloads/Laravel/progressos/docs/api.md`
- `/Users/oirsoy/Downloads/Laravel/progressos/docs/openapi.yaml`
- `/Users/oirsoy/Downloads/Laravel/progressos/routes/api.php`
- `/Users/oirsoy/Downloads/Laravel/progressos/routes/api/v1.php`
- `/Users/oirsoy/Downloads/Laravel/progressos/app/Http/Requests/QuickCaptureRequest.php`
- `/Users/oirsoy/Downloads/Laravel/progressos/app/Http/Controllers/Api/CaptureController.php`
- Local bot files under `src/progressos_bot/`

## Autentikasi

External tools memakai Laravel Sanctum personal access token.

Recommended abilities untuk bot:

```json
["read", "write", "capture"]
```

Tambahkan `reports` hanya jika bot akan mengambil laporan mingguan/bulanan atau export.

Header utama:

```http
Authorization: Bearer pos_xxx
Accept: application/json
Content-Type: application/json
```

## Endpoint Utama Untuk Bot

```http
POST /api/v1/quick-capture
```

Payload valid:

```json
{
  "type": "task",
  "title": "Implementasi webhook Telegram",
  "project_name": "ProgressOS",
  "notes": "Gunakan python-telegram-bot v20",
  "date": "2026-06-20",
  "duration_minutes": 30
}
```

Validasi Laravel:

- `type`: required, one of `task`, `work_log`, `daily_progress`, `learning`, `blocker`
- `title`: required, string, max 180
- `date`: nullable date
- `notes`: nullable string
- `project_name`: nullable string, max 120
- `duration_minutes`: nullable integer, min 1, max 10000

Gunakan header `Idempotency-Key` untuk mencegah duplikasi saat retry. Key bisa dibuat dari channel, chat/user id, message id, dan hash payload.

Response sukses berisi `message`, `record`, dan `record_path`.

## Modul API Yang Tersedia

Read endpoints:

- Dashboard: `GET /api/v1/dashboard`
- Analytics: `GET /api/v1/analytics`
- Standup: `GET /api/v1/standup`
- Projects: `GET /api/v1/projects`, `GET /api/v1/projects/{id}`
- Daily Progress: list/detail
- Work Logs: list/detail
- Tasks: list/detail, kanban, overdue count
- Learning: list/detail, stats, heatmap
- Milestones: list/detail, history
- Habits: list
- Goals: list/detail
- Notifications: list, unread count
- Docs: list/detail/categories, file download
- Reports: weekly/monthly, snapshots
- Search: global search
- Activity: audit feed
- Saved Views: list
- Configuration: read settings/backup/mail notification config

Write endpoints:

- Quick Capture
- CRUD tasks, work logs, daily progress, learning, milestones
- Update task status
- Habits create/update/delete/log/unlog/reorder
- Goals and key results CRUD
- Notifications mark-read/clear
- Docs CRUD and file upload/delete
- References create/delete
- Saved views create/delete/set-default
- Reports snapshots
- Configuration settings, mail, auth, backup connection/sync

Other routes:

- Game APIs exist for 2048, memory, melody, pitch, minesweeper, and sudoku. These are present in routes but should be audited further before bot integration.

## Implementasi Yang Paling Cocok Di Project Ini

Prioritas 1:

- Migrasi ProgressOS client dari `/api/assistant/actions` ke `/api/v1/quick-capture`.
- Ganti schema parser menjadi quick capture payload.
- Support capture type: `task`, `blocker`, `work_log`, `daily_progress`, `learning`.
- Tambahkan `Idempotency-Key`.
- Update tests untuk semua capture type.

Prioritas 2:

- Command read-only:
  - `/standup`
  - `/dashboard`
  - `/search <query>`
  - `/overdue`
  - `/kanban`
  - `/learning_stats`
- Response harus diringkas untuk chat, bukan dump JSON mentah.

Prioritas 3:

- Aksi operasional ringan:
  - update task status
  - log/unlog habit
  - mark notification read
  - create report snapshot

Prioritas 4:

- CRUD penuh untuk goals, key results, docs, references, saved views.
- File handling untuk docs dan report export.
- Discord adapter atau adapter bot lain.

## Perubahan Arsitektur Yang Disarankan

Gunakan boundary ini:

- `channels/telegram`: Telegram polling/webhook adapter.
- `channels/discord`: adapter masa depan.
- `ai`: parser natural language ke action internal.
- `progressos_client`: HTTP client ke Laravel API.
- `schemas`: kontrak action internal dan ProgressOS payload.

Channel adapter hanya mengurus input/output channel. Parser dan ProgressOS client tidak boleh bergantung pada Telegram-specific object.

## Gap Yang Ditemukan Saat Audit

- Pydantic schema hanya mendukung `create_task`.
- Prompt hanya menginstruksikan `create_task` dan `unsupported`.
- HTTP client mengharapkan response `status`, `message`, `action_id`, bukan response `quick-capture`.

Sudah dirapikan pada sesi ini:

- Nama package di `pyproject.toml` menjadi `progressos-bot`.
- README memosisikan project sebagai multi-channel bot gateway.
- `.env.example` dan config default mengarah ke `/api/v1/quick-capture`.
- Roadmap dan API contract tidak lagi memakai endpoint draft `/api/assistant/actions` sebagai target utama.

## Catatan Keamanan

- Jangan expose token ProgressOS, Telegram, Groq, atau Discord di log.
- Tetap wajib user confirmation sebelum write action.
- AI output harus selalu divalidasi lokal dan divalidasi lagi oleh Laravel.
- Untuk multi-user production, perlu mapping channel user id ke ProgressOS user/permission.
- Untuk configuration endpoints, hindari akses via bot kecuali ada allowlist dan confirmation ekstra.
