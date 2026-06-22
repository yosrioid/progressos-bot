from datetime import UTC, datetime

from progressos_bot.retry_queue import (
    DeadLetteredProgressOSSubmission,
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
    queue = InMemoryRetryQueue(dead_letter_after_attempts=10)
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
    assert submissions[0].attempt_count == 5
    assert submissions[0].last_error == "TimeoutException"
    assert submissions[0].quick_capture.notes == "retry updated"
    assert queue.list_dead_letters() == []


def test_in_memory_retry_queue_moves_repeated_failures_to_dead_letter() -> None:
    now = datetime(2026, 6, 22, 9, 32, tzinfo=UTC)
    queue = InMemoryRetryQueue(dead_letter_after_attempts=5, clock=lambda: now)
    queue.enqueue(make_submission())
    queue.enqueue(
        QueuedProgressOSSubmission(
            idempotency_key="fixed-key",
            quick_capture=ProgressOSQuickCaptureRequest(
                type="task",
                title="Follow up invoice client A",
                notes="retry exhausted",
            ),
            queued_at=datetime(2026, 6, 22, 9, 31, tzinfo=UTC),
            attempt_count=3,
            last_error="TimeoutException",
        )
    )

    assert queue.list_all() == []
    assert queue.list_dead_letters() == [
        DeadLetteredProgressOSSubmission(
            idempotency_key="fixed-key",
            quick_capture=ProgressOSQuickCaptureRequest(
                type="task",
                title="Follow up invoice client A",
                notes="retry exhausted",
            ),
            queued_at=datetime(2026, 6, 22, 9, 30, tzinfo=UTC),
            dead_lettered_at=now,
            attempt_count=5,
            last_error="TimeoutException",
        )
    ]


def test_sqlite_retry_queue_rehydrates_submission(tmp_path) -> None:
    path = tmp_path / "retry.sqlite3"
    first_queue = SQLiteRetryQueue(path=str(path))
    first_queue.enqueue(make_submission())

    second_queue = SQLiteRetryQueue(path=str(path))
    submissions = second_queue.list_all()

    assert len(submissions) == 1
    assert submissions[0] == make_submission()


def test_sqlite_retry_queue_rehydrates_dead_letter(tmp_path) -> None:
    path = tmp_path / "retry.sqlite3"
    now = datetime(2026, 6, 22, 9, 32, tzinfo=UTC)
    first_queue = SQLiteRetryQueue(
        path=str(path),
        dead_letter_after_attempts=5,
        clock=lambda: now,
    )
    first_queue.enqueue(make_submission())
    first_queue.enqueue(
        QueuedProgressOSSubmission(
            idempotency_key="fixed-key",
            quick_capture=ProgressOSQuickCaptureRequest(
                type="task",
                title="Follow up invoice client A",
                notes="retry exhausted",
            ),
            queued_at=datetime(2026, 6, 22, 9, 31, tzinfo=UTC),
            attempt_count=3,
            last_error="TimeoutException",
        )
    )

    second_queue = SQLiteRetryQueue(path=str(path), dead_letter_after_attempts=5)

    assert second_queue.list_all() == []
    assert second_queue.list_dead_letters() == [
        DeadLetteredProgressOSSubmission(
            idempotency_key="fixed-key",
            quick_capture=ProgressOSQuickCaptureRequest(
                type="task",
                title="Follow up invoice client A",
                notes="retry exhausted",
            ),
            queued_at=datetime(2026, 6, 22, 9, 30, tzinfo=UTC),
            dead_lettered_at=now,
            attempt_count=5,
            last_error="TimeoutException",
        )
    ]
