import logging
from dataclasses import dataclass, field
from typing import Protocol

from progressos_bot.observability.redaction import redact_mapping, redact_text

logger = logging.getLogger(__name__)


class ErrorReporter(Protocol):
    def report(
        self,
        error: BaseException,
        *,
        correlation_id: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None: ...


class NoopErrorReporter:
    def report(
        self,
        error: BaseException,
        *,
        correlation_id: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        del error, correlation_id, context


class LoggingErrorReporter:
    def report(
        self,
        error: BaseException,
        *,
        correlation_id: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        extra: dict[str, object] = {}
        if correlation_id:
            extra["correlation_id"] = correlation_id
        if context:
            extra["error_context"] = redact_mapping(context)

        logger.error(
            "Reported error: %s",
            redact_text(str(error)),
            extra=extra,
            exc_info=(type(error), error, error.__traceback__),
        )


@dataclass
class InMemoryErrorReporter:
    reports: list[dict[str, object]] = field(default_factory=list)

    def report(
        self,
        error: BaseException,
        *,
        correlation_id: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        self.reports.append(
            {
                "message": redact_text(str(error)),
                "correlation_id": correlation_id,
                "context": redact_mapping(context or {}),
            }
        )
