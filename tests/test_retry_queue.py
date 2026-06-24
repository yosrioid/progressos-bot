import json
from datetime import UTC, datetime

import pytest

from progressos_bot.retry_queue import (
    DeadLetteredProgressOSSubmission,
    InMemoryRetryQueue,
    QueuedProgressOSSubmission,
    SQLiteRetryQueue,
    build_retry_queue_diagnostic_bundle,
    summarize_dead_letters,
    summarize_retry_queue,
)
from progressos_bot.retry_queue_cli import main as retry_queue_cli_main
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


def test_in_memory_retry_queue_requeues_dead_letter_with_same_idempotency_key() -> None:
    queue = InMemoryRetryQueue(dead_letter_after_attempts=2)
    queue.enqueue(make_submission())

    queued = queue.requeue_dead_letter("fixed-key")

    assert queued is not None
    assert queued.idempotency_key == "fixed-key"
    assert queued.attempt_count == 2
    assert queue.list_dead_letters() == []
    assert queue.list_all() == [queued]


def test_sqlite_retry_queue_requeues_dead_letter_with_same_idempotency_key(tmp_path) -> None:
    path = tmp_path / "retry.sqlite3"
    queue = SQLiteRetryQueue(path=str(path), dead_letter_after_attempts=2)
    queue.enqueue(make_submission())

    queued = queue.requeue_dead_letter("fixed-key")

    assert queued is not None
    assert queued.idempotency_key == "fixed-key"
    assert queued.attempt_count == 2

    second_queue = SQLiteRetryQueue(path=str(path), dead_letter_after_attempts=2)
    assert second_queue.list_dead_letters() == []
    assert second_queue.list_all() == [queued]


def test_sqlite_retry_queue_discards_dead_letter(tmp_path) -> None:
    path = tmp_path / "retry.sqlite3"
    queue = SQLiteRetryQueue(path=str(path), dead_letter_after_attempts=2)
    queue.enqueue(make_submission())

    discarded = queue.discard_dead_letter("fixed-key")

    assert discarded is not None
    assert discarded.idempotency_key == "fixed-key"
    assert queue.list_dead_letters() == []
    assert queue.list_all() == []


def test_retry_queue_summary_counts_queued_and_dead_letters() -> None:
    queue = InMemoryRetryQueue(dead_letter_after_attempts=3)
    queue.enqueue(make_submission())
    queue.enqueue(
        QueuedProgressOSSubmission(
            idempotency_key="dead-key",
            quick_capture=ProgressOSQuickCaptureRequest(
                type="task",
                title="Fix webhook retry",
            ),
            queued_at=datetime(2026, 6, 22, 9, 31, tzinfo=UTC),
            attempt_count=3,
            last_error="HTTP 503",
        )
    )

    counts = summarize_retry_queue(queue)

    assert counts.queued_count == 1
    assert counts.dead_letter_count == 1


def test_dead_letter_summary_redacts_operator_metadata() -> None:
    now = datetime(2026, 6, 22, 9, 32, tzinfo=UTC)
    queue = InMemoryRetryQueue(dead_letter_after_attempts=3, clock=lambda: now)
    queue.enqueue(
        QueuedProgressOSSubmission(
            idempotency_key="fixed-key",
            quick_capture=ProgressOSQuickCaptureRequest(
                type="task",
                title="Rotate bearer token=secret-value",
                notes="Original message includes token=should-not-print",
            ),
            queued_at=datetime(2026, 6, 22, 9, 30, tzinfo=UTC),
            attempt_count=3,
            last_error="authorization: Bearer abc.def",
        )
    )

    summaries = summarize_dead_letters(queue)

    assert len(summaries) == 1
    assert summaries[0].status == "dead_lettered"
    assert summaries[0].idempotency_key == "fixed-key"
    assert summaries[0].capture_type == "task"
    assert summaries[0].title == "Rotate bearer token=[redacted]"
    assert summaries[0].queued_at == datetime(2026, 6, 22, 9, 30, tzinfo=UTC)
    assert summaries[0].dead_lettered_at == now
    assert summaries[0].attempt_count == 3
    assert summaries[0].last_error == "authorization: Bearer [redacted]"
    assert "should-not-print" not in summaries[0].model_dump_json()


def test_retry_queue_diagnostic_bundle_includes_redacted_matching_metadata() -> None:
    generated_at = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)
    queue = InMemoryRetryQueue(dead_letter_after_attempts=3, clock=lambda: generated_at)
    queue.enqueue(
        QueuedProgressOSSubmission(
            idempotency_key="fixed-key",
            quick_capture=ProgressOSQuickCaptureRequest(
                type="task",
                title="Rotate progressos_token=secret-value",
                notes="Original message includes token=should-not-print",
            ),
            queued_at=datetime(2026, 6, 22, 9, 30, tzinfo=UTC),
            attempt_count=3,
            last_error="authorization: Bearer abc.def",
        )
    )

    bundle = build_retry_queue_diagnostic_bundle(
        queue,
        correlation_id="corr-123",
        idempotency_key="fixed-key",
        clock=lambda: generated_at,
    )

    dumped = bundle.model_dump_json()
    assert bundle.correlation_id == "corr-123"
    assert bundle.generated_at == generated_at
    assert bundle.retry_queue.counts.queued_count == 0
    assert bundle.retry_queue.counts.dead_letter_count == 1
    assert bundle.retry_queue.queued_matches == []
    assert len(bundle.retry_queue.dead_letter_matches) == 1
    assert bundle.retry_queue.dead_letter_matches[0].title == (
        "Rotate progressos_token=[redacted]"
    )
    assert bundle.retry_queue.dead_letter_matches[0].last_error == (
        "authorization: Bearer [redacted]"
    )
    assert "secret-value" not in dumped
    assert "should-not-print" not in dumped


def test_retry_queue_cli_prints_status_json(tmp_path, capsys) -> None:
    path = tmp_path / "retry.sqlite3"
    queue = SQLiteRetryQueue(path=str(path))
    queue.enqueue(make_submission())

    exit_code = retry_queue_cli_main(["--path", str(path), "status"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {
        "queued_count": 1,
        "dead_letter_count": 0,
    }


def test_retry_queue_cli_prints_redacted_dead_letter_json(tmp_path, capsys) -> None:
    path = tmp_path / "retry.sqlite3"
    now = datetime(2026, 6, 22, 9, 32, tzinfo=UTC)
    queue = SQLiteRetryQueue(
        path=str(path),
        dead_letter_after_attempts=3,
        clock=lambda: now,
    )
    queue.enqueue(
        QueuedProgressOSSubmission(
            idempotency_key="fixed-key",
            quick_capture=ProgressOSQuickCaptureRequest(
                type="task",
                title="Rotate bearer token=secret-value",
                notes="Original message includes token=should-not-print",
            ),
            queued_at=datetime(2026, 6, 22, 9, 30, tzinfo=UTC),
            attempt_count=3,
            last_error="authorization: Bearer abc.def",
        )
    )

    exit_code = retry_queue_cli_main(["--path", str(path), "dead-letters"])

    captured = capsys.readouterr()
    assert exit_code == 0
    parsed = json.loads(captured.out)
    assert parsed == [
        {
            "status": "dead_lettered",
            "idempotency_key": "fixed-key",
            "capture_type": "task",
            "title": "Rotate bearer token=[redacted]",
            "queued_at": "2026-06-22T09:30:00Z",
            "dead_lettered_at": "2026-06-22T09:32:00Z",
            "attempt_count": 3,
            "last_error": "authorization: Bearer [redacted]",
        }
    ]
    assert "should-not-print" not in captured.out


def test_retry_queue_cli_requeue_requires_matching_confirmation(tmp_path) -> None:
    path = tmp_path / "retry.sqlite3"
    queue = SQLiteRetryQueue(path=str(path), dead_letter_after_attempts=2)
    queue.enqueue(make_submission())

    with pytest.raises(SystemExit) as exc_info:
        retry_queue_cli_main(
            [
                "--path",
                str(path),
                "requeue",
                "--idempotency-key",
                "fixed-key",
                "--confirm",
                "wrong-key",
            ]
        )

    assert exc_info.value.code == 2
    assert SQLiteRetryQueue(path=str(path), dead_letter_after_attempts=2).list_all() == []


def test_retry_queue_cli_requeues_dead_letter(tmp_path, capsys) -> None:
    path = tmp_path / "retry.sqlite3"
    queue = SQLiteRetryQueue(path=str(path), dead_letter_after_attempts=2)
    queue.enqueue(make_submission())

    exit_code = retry_queue_cli_main(
        [
            "--path",
            str(path),
            "requeue",
            "--idempotency-key",
            "fixed-key",
            "--confirm",
            "fixed-key",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {
        "action": "requeued",
        "idempotency_key": "fixed-key",
        "attempt_count": 2,
    }
    second_queue = SQLiteRetryQueue(path=str(path), dead_letter_after_attempts=2)
    assert second_queue.list_dead_letters() == []
    assert len(second_queue.list_all()) == 1
    assert second_queue.list_all()[0].idempotency_key == "fixed-key"


def test_retry_queue_cli_discards_dead_letter(tmp_path, capsys) -> None:
    path = tmp_path / "retry.sqlite3"
    queue = SQLiteRetryQueue(path=str(path), dead_letter_after_attempts=2)
    queue.enqueue(make_submission())

    exit_code = retry_queue_cli_main(
        [
            "--path",
            str(path),
            "discard",
            "--idempotency-key",
            "fixed-key",
            "--confirm",
            "fixed-key",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {
        "action": "discarded",
        "idempotency_key": "fixed-key",
        "attempt_count": 2,
    }
    second_queue = SQLiteRetryQueue(path=str(path), dead_letter_after_attempts=2)
    assert second_queue.list_dead_letters() == []
    assert second_queue.list_all() == []


def test_retry_queue_cli_prints_diagnostic_bundle(tmp_path, capsys) -> None:
    path = tmp_path / "retry.sqlite3"
    queue = SQLiteRetryQueue(path=str(path), dead_letter_after_attempts=2)
    queue.enqueue(
        QueuedProgressOSSubmission(
            idempotency_key="fixed-key",
            quick_capture=ProgressOSQuickCaptureRequest(
                type="task",
                title="Rotate progressos_token=secret-value",
                notes="Original message includes token=should-not-print",
            ),
            queued_at=datetime(2026, 6, 22, 9, 30, tzinfo=UTC),
            attempt_count=2,
            last_error="authorization: Bearer abc.def",
        )
    )

    exit_code = retry_queue_cli_main(
        [
            "--path",
            str(path),
            "diagnostic-bundle",
            "--correlation-id",
            "corr-123",
            "--idempotency-key",
            "fixed-key",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    parsed = json.loads(captured.out)
    assert parsed["correlation_id"] == "corr-123"
    assert parsed["retry_queue"]["counts"] == {
        "queued_count": 0,
        "dead_letter_count": 1,
    }
    assert parsed["retry_queue"]["queued_matches"] == []
    assert parsed["retry_queue"]["dead_letter_matches"][0]["title"] == (
        "Rotate progressos_token=[redacted]"
    )
    assert "secret-value" not in captured.out
    assert "should-not-print" not in captured.out
