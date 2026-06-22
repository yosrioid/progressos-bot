import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from progressos_bot.schemas import ProgressOSQuickCaptureRequest


class QueuedProgressOSSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1)
    quick_capture: ProgressOSQuickCaptureRequest
    queued_at: datetime
    attempt_count: int = Field(ge=1)
    last_error: str = Field(min_length=1, max_length=500)


class RetryQueue(Protocol):
    def enqueue(self, submission: QueuedProgressOSSubmission) -> None: ...

    def list_all(self) -> list[QueuedProgressOSSubmission]: ...


class InMemoryRetryQueue:
    def __init__(self) -> None:
        self._submissions: dict[str, QueuedProgressOSSubmission] = {}

    def enqueue(self, submission: QueuedProgressOSSubmission) -> None:
        self._submissions[submission.idempotency_key] = submission

    def list_all(self) -> list[QueuedProgressOSSubmission]:
        return list(self._submissions.values())


class SQLiteRetryQueue:
    def __init__(self, *, path: str) -> None:
        queue_path = Path(path).expanduser()
        self._path = str(queue_path)
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def enqueue(self, submission: QueuedProgressOSSubmission) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO retry_submissions (
                    idempotency_key,
                    quick_capture_json,
                    queued_at,
                    attempt_count,
                    last_error
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    quick_capture_json = excluded.quick_capture_json,
                    queued_at = excluded.queued_at,
                    attempt_count = excluded.attempt_count,
                    last_error = excluded.last_error
                """,
                (
                    submission.idempotency_key,
                    submission.quick_capture.model_dump_json(),
                    self._format_datetime(submission.queued_at),
                    submission.attempt_count,
                    submission.last_error,
                ),
            )

    def list_all(self) -> list[QueuedProgressOSSubmission]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT idempotency_key, quick_capture_json, queued_at, attempt_count, last_error
                FROM retry_submissions
                ORDER BY queued_at ASC, idempotency_key ASC
                """
            ).fetchall()

        submissions: list[QueuedProgressOSSubmission] = []
        for row in rows:
            submissions.append(
                QueuedProgressOSSubmission(
                    idempotency_key=row["idempotency_key"],
                    quick_capture=ProgressOSQuickCaptureRequest.model_validate_json(
                        row["quick_capture_json"]
                    ),
                    queued_at=self._parse_datetime(row["queued_at"]),
                    attempt_count=row["attempt_count"],
                    last_error=row["last_error"],
                )
            )
        return submissions

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS retry_submissions (
                    idempotency_key TEXT PRIMARY KEY,
                    quick_capture_json TEXT NOT NULL,
                    queued_at TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    last_error TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
