from dataclasses import dataclass
from typing import Literal, Protocol

from progressos_bot.pending import PendingActionStore
from progressos_bot.schemas import (
    ParsedAction,
    ProgressOSActionRequest,
    ProgressOSActionResponse,
)

CaptureDraftStatus = Literal["confirmation_required", "unsupported"]


class ActionParser(Protocol):
    async def parse(self, message: str) -> ParsedAction: ...


class ProgressOSActionSubmitter(Protocol):
    async def submit_action(self, request: ProgressOSActionRequest) -> ProgressOSActionResponse: ...


@dataclass(frozen=True)
class CaptureDraftResult:
    status: CaptureDraftStatus
    user_message: str


@dataclass(frozen=True)
class CaptureSubmitResult:
    submitted: bool
    user_message: str


class CaptureFlow:
    def __init__(
        self,
        *,
        parser: ActionParser,
        progressos: ProgressOSActionSubmitter,
        pending: PendingActionStore,
    ) -> None:
        self._parser = parser
        self._progressos = progressos
        self._pending = pending

    async def begin_capture(self, *, user_key: str, original_text: str) -> CaptureDraftResult:
        action = await self._parser.parse(original_text)
        if action.intent == "unsupported":
            return CaptureDraftResult(
                status="unsupported",
                user_message=action.user_confirmation_text,
            )

        self._pending.put(user_key, original_text, action)
        return CaptureDraftResult(
            status="confirmation_required",
            user_message=action.user_confirmation_text,
        )

    def cancel_capture(self, *, user_key: str) -> None:
        self._pending.discard(user_key)

    async def submit_confirmed_capture(
        self,
        *,
        user_key: str,
        source: str = "telegram",
        source_user_id: str,
        source_chat_id: str,
        progressos_user_id: str | None,
    ) -> CaptureSubmitResult:
        pending = self._pending.pop(user_key)
        if pending is None:
            return CaptureSubmitResult(
                submitted=False,
                user_message="Tidak ada draft aktif atau draft sudah kedaluwarsa.",
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
        return CaptureSubmitResult(
            submitted=True,
            user_message=response.to_user_message(),
        )
