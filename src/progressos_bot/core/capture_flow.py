from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import Literal, Protocol

from progressos_bot.observability.correlation import CorrelationIdFactory
from progressos_bot.observability.metrics import MetricsSink, NoopMetricsSink
from progressos_bot.pending import PendingActionStore
from progressos_bot.schemas import (
    ParsedAction,
    ProgressOSActionRequest,
    ProgressOSActionResponse,
)

CaptureDraftStatus = Literal["confirmation_required", "unsupported"]
CAPTURE_INTENTS = frozenset(
    (
        "create_task",
        "create_blocker",
        "log_work",
        "log_daily_progress",
        "capture_learning",
    )
)


class ActionParser(Protocol):
    async def parse(self, message: str) -> ParsedAction: ...


class ProgressOSActionSubmitter(Protocol):
    async def submit_action(self, request: ProgressOSActionRequest) -> ProgressOSActionResponse: ...


@dataclass(frozen=True)
class CaptureDraftResult:
    status: CaptureDraftStatus
    user_message: str
    correlation_id: str


@dataclass(frozen=True)
class CaptureSubmitResult:
    submitted: bool
    user_message: str
    correlation_id: str


class CaptureFlow:
    def __init__(
        self,
        *,
        parser: ActionParser,
        progressos: ProgressOSActionSubmitter,
        pending: PendingActionStore,
        correlation_id_factory: Callable[[], str] | None = None,
        metrics: MetricsSink | None = None,
        enabled_intents: Collection[str] | None = None,
    ) -> None:
        self._parser = parser
        self._progressos = progressos
        self._pending = pending
        self._new_correlation_id = correlation_id_factory or CorrelationIdFactory().new
        self._metrics = metrics or NoopMetricsSink()
        self._enabled_intents = (
            CAPTURE_INTENTS if enabled_intents is None else frozenset(enabled_intents)
        )

    async def begin_capture(self, *, user_key: str, original_text: str) -> CaptureDraftResult:
        correlation_id = self._new_correlation_id()
        action = await self._parser.parse(original_text)
        if action.intent == "unsupported":
            self._metrics.increment("capture_parse_total", outcome="unsupported")
            return CaptureDraftResult(
                status="unsupported",
                user_message=action.user_confirmation_text,
                correlation_id=correlation_id,
            )

        if action.intent not in self._enabled_intents:
            self._metrics.increment("capture_parse_total", outcome="disabled")
            return CaptureDraftResult(
                status="unsupported",
                user_message=f"Intent {action.intent} sedang dinonaktifkan admin.",
                correlation_id=correlation_id,
            )

        self._metrics.increment("capture_parse_total", outcome="supported")
        self._metrics.increment("capture_confirmation_total", outcome="requested")
        self._pending.put(user_key, original_text, action)
        return CaptureDraftResult(
            status="confirmation_required",
            user_message=action.user_confirmation_text,
            correlation_id=correlation_id,
        )

    def cancel_capture(self, *, user_key: str) -> None:
        self._pending.discard(user_key)
        self._metrics.increment("capture_confirmation_total", outcome="cancelled")

    async def submit_confirmed_capture(
        self,
        *,
        user_key: str,
        source: str = "telegram",
        source_user_id: str,
        source_chat_id: str,
        progressos_user_id: str | None,
    ) -> CaptureSubmitResult:
        correlation_id = self._new_correlation_id()
        pending = self._pending.pop(user_key)
        if pending is None:
            self._metrics.increment("capture_submit_total", outcome="missing_draft")
            return CaptureSubmitResult(
                submitted=False,
                user_message="Tidak ada draft aktif atau draft sudah kedaluwarsa.",
                correlation_id=correlation_id,
            )

        request = ProgressOSActionRequest(
            source=source,
            source_user_id=source_user_id,
            source_chat_id=source_chat_id,
            progressos_user_id=progressos_user_id,
            original_text=pending.original_text,
            parsed_action=pending.parsed_action,
        )
        response = await self._progressos.submit_action(request)
        self._metrics.increment("capture_submit_total", outcome="success")
        return CaptureSubmitResult(
            submitted=True,
            user_message=response.to_user_message(),
            correlation_id=correlation_id,
        )
