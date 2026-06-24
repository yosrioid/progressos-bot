import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from progressos_bot.observability.redaction import redact_text
from progressos_bot.schemas import ProgressOSQuickCaptureRequest


class QueuedProgressOSSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1)
    quick_capture: ProgressOSQuickCaptureRequest
    queued_at: datetime
    attempt_count: int = Field(ge=1)
    last_error: str = Field(min_length=1, max_length=500)


class DeadLetteredProgressOSSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1)
    quick_capture: ProgressOSQuickCaptureRequest
    queued_at: datetime
    dead_lettered_at: datetime
    attempt_count: int = Field(ge=1)
    last_error: str = Field(min_length=1, max_length=500)


class RetryQueueCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued_count: int = Field(ge=0)
    dead_letter_count: int = Field(ge=0)


class RetryQueueSubmissionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["queued", "dead_lettered"]
    idempotency_key: str = Field(min_length=1)
    capture_type: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=180)
    queued_at: datetime
    dead_lettered_at: datetime | None = None
    attempt_count: int = Field(ge=1)
    last_error: str = Field(min_length=1, max_length=500)


class RetryQueue(Protocol):
    def enqueue(self, submission: QueuedProgressOSSubmission) -> None: ...

    def list_all(self) -> list[QueuedProgressOSSubmission]: ...

    def list_dead_letters(self) -> list[DeadLetteredProgressOSSubmission]: ...


def summarize_retry_queue(queue: RetryQueue) -> RetryQueueCounts:
    return RetryQueueCounts(
        queued_count=len(queue.list_all()),
        dead_letter_count=len(queue.list_dead_letters()),
    )


def summarize_dead_letters(queue: RetryQueue) -> list[RetryQueueSubmissionSummary]:
    return [
        _summarize_dead_letter(submission)
        for submission in queue.list_dead_letters()
    ]


def _summarize_dead_letter(
    submission: DeadLetteredProgressOSSubmission,
) -> RetryQueueSubmissionSummary:
    return RetryQueueSubmissionSummary(
        status="dead_lettered",
        idempotency_key=submission.idempotency_key,
        capture_type=submission.quick_capture.type,
        title=redact_text(submission.quick_capture.title),
        queued_at=submission.queued_at,
        dead_lettered_at=submission.dead_lettered_at,
        attempt_count=submission.attempt_count,
        last_error=redact_text(submission.last_error),
    )


class InMemoryRetryQueue:
    def __init__(
        self,
        *,
        dead_letter_after_attempts: int = 5,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._dead_letter_after_attempts = max(1, dead_letter_after_attempts)
        self._clock = clock or self._utc_now
        self._submissions: dict[str, QueuedProgressOSSubmission] = {}
        self._dead_letters: dict[str, DeadLetteredProgressOSSubmission] = {}

    def enqueue(self, submission: QueuedProgressOSSubmission) -> None:
        existing_dead_letter = self._dead_letters.get(submission.idempotency_key)
        if existing_dead_letter:
            self._dead_letters[submission.idempotency_key] = existing_dead_letter.model_copy(
                update={
                    "quick_capture": submission.quick_capture,
                    "dead_lettered_at": self._now(),
                    "attempt_count": existing_dead_letter.attempt_count
                    + submission.attempt_count,
                    "last_error": submission.last_error,
                }
            )
            return

        existing = self._submissions.get(submission.idempotency_key)
        attempt_count = submission.attempt_count
        queued_at = submission.queued_at
        if existing:
            attempt_count += existing.attempt_count
            queued_at = existing.queued_at

        merged = submission.model_copy(
            update={"attempt_count": attempt_count, "queued_at": queued_at}
        )
        if attempt_count >= self._dead_letter_after_attempts:
            self._submissions.pop(submission.idempotency_key, None)
            self._dead_letters[submission.idempotency_key] = DeadLetteredProgressOSSubmission(
                idempotency_key=merged.idempotency_key,
                quick_capture=merged.quick_capture,
                queued_at=merged.queued_at,
                dead_lettered_at=self._now(),
                attempt_count=merged.attempt_count,
                last_error=merged.last_error,
            )
            return

        self._submissions[submission.idempotency_key] = merged

    def list_all(self) -> list[QueuedProgressOSSubmission]:
        return list(self._submissions.values())

    def list_dead_letters(self) -> list[DeadLetteredProgressOSSubmission]:
        return list(self._dead_letters.values())

    def requeue_dead_letter(self, idempotency_key: str) -> QueuedProgressOSSubmission | None:
        dead_letter = self._dead_letters.pop(idempotency_key, None)
        if dead_letter is None:
            return None

        queued = QueuedProgressOSSubmission(
            idempotency_key=dead_letter.idempotency_key,
            quick_capture=dead_letter.quick_capture,
            queued_at=dead_letter.queued_at,
            attempt_count=dead_letter.attempt_count,
            last_error=dead_letter.last_error,
        )
        self._submissions[idempotency_key] = queued
        return queued

    def discard_dead_letter(self, idempotency_key: str) -> DeadLetteredProgressOSSubmission | None:
        return self._dead_letters.pop(idempotency_key, None)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)


class SQLiteRetryQueue:
    def __init__(
        self,
        *,
        path: str,
        dead_letter_after_attempts: int = 5,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        queue_path = Path(path).expanduser()
        self._path = str(queue_path)
        self._dead_letter_after_attempts = max(1, dead_letter_after_attempts)
        self._clock = clock or self._utc_now
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def enqueue(self, submission: QueuedProgressOSSubmission) -> None:
        with self._connect() as connection:
            existing_dead_letter = connection.execute(
                """
                SELECT queued_at, attempt_count
                FROM retry_dead_letters
                WHERE idempotency_key = ?
                """,
                (submission.idempotency_key,),
            ).fetchone()
            if existing_dead_letter:
                connection.execute(
                    """
                    UPDATE retry_dead_letters
                    SET
                        quick_capture_json = ?,
                        dead_lettered_at = ?,
                        attempt_count = ?,
                        last_error = ?
                    WHERE idempotency_key = ?
                    """,
                    (
                        submission.quick_capture.model_dump_json(),
                        self._format_datetime(self._now()),
                        existing_dead_letter["attempt_count"] + submission.attempt_count,
                        submission.last_error,
                        submission.idempotency_key,
                    ),
                )
                return

            existing = connection.execute(
                """
                SELECT queued_at, attempt_count
                FROM retry_submissions
                WHERE idempotency_key = ?
                """,
                (submission.idempotency_key,),
            ).fetchone()

            attempt_count = submission.attempt_count
            queued_at = submission.queued_at
            if existing:
                attempt_count += existing["attempt_count"]
                queued_at = self._parse_datetime(existing["queued_at"])

            if attempt_count >= self._dead_letter_after_attempts:
                connection.execute(
                    "DELETE FROM retry_submissions WHERE idempotency_key = ?",
                    (submission.idempotency_key,),
                )
                connection.execute(
                    """
                    INSERT INTO retry_dead_letters (
                        idempotency_key,
                        quick_capture_json,
                        queued_at,
                        dead_lettered_at,
                        attempt_count,
                        last_error
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(idempotency_key) DO UPDATE SET
                        quick_capture_json = excluded.quick_capture_json,
                        queued_at = excluded.queued_at,
                        dead_lettered_at = excluded.dead_lettered_at,
                        attempt_count = excluded.attempt_count,
                        last_error = excluded.last_error
                    """,
                    (
                        submission.idempotency_key,
                        submission.quick_capture.model_dump_json(),
                        self._format_datetime(queued_at),
                        self._format_datetime(self._now()),
                        attempt_count,
                        submission.last_error,
                    ),
                )
                return

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
                    self._format_datetime(queued_at),
                    attempt_count,
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

    def list_dead_letters(self) -> list[DeadLetteredProgressOSSubmission]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    idempotency_key,
                    quick_capture_json,
                    queued_at,
                    dead_lettered_at,
                    attempt_count,
                    last_error
                FROM retry_dead_letters
                ORDER BY dead_lettered_at ASC, idempotency_key ASC
                """
            ).fetchall()

        submissions: list[DeadLetteredProgressOSSubmission] = []
        for row in rows:
            submissions.append(self._dead_letter_from_row(row))
        return submissions

    def requeue_dead_letter(self, idempotency_key: str) -> QueuedProgressOSSubmission | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    idempotency_key,
                    quick_capture_json,
                    queued_at,
                    dead_lettered_at,
                    attempt_count,
                    last_error
                FROM retry_dead_letters
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if row is None:
                return None

            queued = self._queued_from_dead_letter_row(row)
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
                    queued.idempotency_key,
                    queued.quick_capture.model_dump_json(),
                    self._format_datetime(queued.queued_at),
                    queued.attempt_count,
                    queued.last_error,
                ),
            )
            connection.execute(
                "DELETE FROM retry_dead_letters WHERE idempotency_key = ?",
                (idempotency_key,),
            )
            return queued

    def discard_dead_letter(self, idempotency_key: str) -> DeadLetteredProgressOSSubmission | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    idempotency_key,
                    quick_capture_json,
                    queued_at,
                    dead_lettered_at,
                    attempt_count,
                    last_error
                FROM retry_dead_letters
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if row is None:
                return None

            dead_letter = self._dead_letter_from_row(row)
            connection.execute(
                "DELETE FROM retry_dead_letters WHERE idempotency_key = ?",
                (idempotency_key,),
            )
            return dead_letter

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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS retry_dead_letters (
                    idempotency_key TEXT PRIMARY KEY,
                    quick_capture_json TEXT NOT NULL,
                    queued_at TEXT NOT NULL,
                    dead_lettered_at TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    last_error TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection

    def _queued_from_dead_letter_row(self, row: sqlite3.Row) -> QueuedProgressOSSubmission:
        return QueuedProgressOSSubmission(
            idempotency_key=row["idempotency_key"],
            quick_capture=ProgressOSQuickCaptureRequest.model_validate_json(
                row["quick_capture_json"]
            ),
            queued_at=self._parse_datetime(row["queued_at"]),
            attempt_count=row["attempt_count"],
            last_error=row["last_error"],
        )

    def _dead_letter_from_row(self, row: sqlite3.Row) -> DeadLetteredProgressOSSubmission:
        return DeadLetteredProgressOSSubmission(
            idempotency_key=row["idempotency_key"],
            quick_capture=ProgressOSQuickCaptureRequest.model_validate_json(
                row["quick_capture_json"]
            ),
            queued_at=self._parse_datetime(row["queued_at"]),
            dead_lettered_at=self._parse_datetime(row["dead_lettered_at"]),
            attempt_count=row["attempt_count"],
            last_error=row["last_error"],
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

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
