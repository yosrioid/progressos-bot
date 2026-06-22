from datetime import UTC, datetime

from progressos_bot.retry_queue import (
    InMemoryRetryQueue,
    QueuedProgressOSSubmission,
    SQLiteRetryQueue,
)
from progressos_bot.schemas import ProgressOSQuickCaptureRequest


def make_submission() -> QueuedProgressOSSubmission:
    return QueuedProgressOSSubmission(
        idempotency_key="fixed-key",
        quick_capture=ProgressOSQuickCaptureRequest(
            type="task",
            title="Follow up invoice client A",
            notes="Original message: buat task follow up invoice client A besok",
        ),
        queued_at=datetime(2026, 6, 22, 9, 30, tzinfo=UTC),
        attempt_count=2,
        last_error="HTTP 503",
    )


def test_in_memory_retry_queue_upserts_by_idempotency_key() -> None:
    queue = InMemoryRetryQueue()
    queue.enqueue(make_submission())
    queue.enqueue(
        QueuedProgressOSSubmission(
            idempotency_key="fixed-key",
            quick_capture=ProgressOSQuickCaptureRequest(
                type="task",
                title="Follow up invoice client A",
                notes="retry updated",
            ),
            queued_at=datetime(2026, 6, 22, 9, 31, tzinfo=UTC),
            attempt_count=3,
            last_error="TimeoutException",
        )
    )

    submissions = queue.list_all()

    assert len(submissions) == 1
    assert submissions[0].idempotency_key == "fixed-key"
    assert submissions[0].attempt_count == 3
    assert submissions[0].last_error == "TimeoutException"
    assert submissions[0].quick_capture.notes == "retry updated"


def test_sqlite_retry_queue_rehydrates_submission(tmp_path) -> None:
    path = tmp_path / "retry.sqlite3"
    first_queue = SQLiteRetryQueue(path=str(path))
    first_queue.enqueue(make_submission())

    second_queue = SQLiteRetryQueue(path=str(path))
    submissions = second_queue.list_all()

    assert len(submissions) == 1
    assert submissions[0] == make_submission()
