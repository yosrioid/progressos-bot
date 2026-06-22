import logging

from progressos_bot.observability.error_reporting import (
    InMemoryErrorReporter,
    LoggingErrorReporter,
    NoopErrorReporter,
)
from progressos_bot.observability.redaction import REDACTED


def test_in_memory_error_reporter_redacts_message_and_context() -> None:
    reporter = InMemoryErrorReporter()

    reporter.report(
        RuntimeError("failed with Bearer secret-token"),
        correlation_id="corr-1",
        context={
            "telegram_token": "123:abc",
            "detail": "progressos_token=secret-value",
            "dependency": "ProgressOS",
        },
    )

    assert reporter.reports == [
        {
            "message": f"failed with Bearer {REDACTED}",
            "correlation_id": "corr-1",
            "context": {
                "telegram_token": REDACTED,
                "detail": f"progressos_token={REDACTED}",
                "dependency": "ProgressOS",
            },
        }
    ]


def test_logging_error_reporter_redacts_context_in_log_record(caplog) -> None:
    reporter = LoggingErrorReporter()

    with caplog.at_level(logging.ERROR):
        reporter.report(
            RuntimeError("failed with Bearer secret-token"),
            correlation_id="corr-1",
            context={"api_key": "secret-key", "dependency": "Groq"},
        )

    record = caplog.records[0]
    assert record.correlation_id == "corr-1"
    assert record.error_context == {"api_key": REDACTED, "dependency": "Groq"}
    assert "secret-token" not in record.getMessage()
    assert f"Bearer {REDACTED}" in record.getMessage()


def test_noop_error_reporter_accepts_errors() -> None:
    reporter = NoopErrorReporter()

    reporter.report(RuntimeError("failed"), correlation_id="corr-1")
