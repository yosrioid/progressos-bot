import json
import logging

from progressos_bot.logging import JsonFormatter, configure_logging


def test_json_formatter_outputs_stable_operational_fields() -> None:
    record = logging.LogRecord(
        name="progressos_bot.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=10,
        msg="Transient ProgressOS failure",
        args=(),
        exc_info=None,
    )
    record.created = 1782118800.0

    payload = json.loads(JsonFormatter().format(record))

    assert payload == {
        "timestamp": "2026-06-22T09:00:00+00:00",
        "level": "WARNING",
        "logger": "progressos_bot.test",
        "message": "Transient ProgressOS failure",
    }


def test_json_formatter_includes_correlation_id_when_present() -> None:
    record = logging.LogRecord(
        name="progressos_bot.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Capture submitted",
        args=(),
        exc_info=None,
    )
    record.correlation_id = "corr-123"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["correlation_id"] == "corr-123"


def test_configure_logging_json_format_writes_json(capsys) -> None:
    configure_logging("INFO", log_format="json")
    logging.getLogger("progressos_bot.test").info("Bot started")

    captured = capsys.readouterr()
    payload = json.loads(captured.err)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "progressos_bot.test"
    assert payload["message"] == "Bot started"
