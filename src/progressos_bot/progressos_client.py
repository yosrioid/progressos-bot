from collections.abc import Callable
from uuid import uuid4

import httpx

from progressos_bot.schemas import (
    CreateTaskPayload,
    ProgressOSActionRequest,
    ProgressOSActionResponse,
    ProgressOSQuickCaptureRequest,
    ProgressOSValidationErrorResponse,
)


class ProgressOSClientError(RuntimeError):
    """Base error for safe ProgressOS client failures."""


class ProgressOSValidationError(ProgressOSClientError):
    def __init__(self, response: ProgressOSValidationErrorResponse) -> None:
        self.response = response
        super().__init__(response.message)


class ProgressOSTransientError(ProgressOSClientError):
    pass


class ProgressOSClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        endpoint: str,
        timeout_seconds: float,
        *,
        idempotency_key_factory: Callable[[], str] | None = None,
        max_attempts: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._timeout = timeout_seconds
        self._idempotency_key_factory = idempotency_key_factory or self._new_idempotency_key
        self._max_attempts = max(1, max_attempts)
        self._transport = transport

    async def submit_action(self, request: ProgressOSActionRequest) -> ProgressOSActionResponse:
        quick_capture = self.build_quick_capture_request(request)
        idempotency_key = self._idempotency_key_factory()
        headers = {**self._headers, "Idempotency-Key": idempotency_key}

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            last_error: httpx.RequestError | None = None

            for attempt in range(1, self._max_attempts + 1):
                try:
                    response = await client.post(
                        f"{self._base_url}{self._endpoint}",
                        headers=headers,
                        json=quick_capture.model_dump(mode="json", exclude_none=True),
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_error = exc
                    if attempt == self._max_attempts:
                        raise ProgressOSTransientError(
                            "ProgressOS belum bisa dihubungi. Coba lagi sebentar."
                        ) from exc
                    continue

                if response.status_code == 422:
                    error = ProgressOSValidationErrorResponse.model_validate(response.json())
                    raise ProgressOSValidationError(error)

                if response.status_code >= 500:
                    if attempt == self._max_attempts:
                        raise ProgressOSTransientError(
                            "ProgressOS sedang bermasalah. Coba lagi sebentar."
                        )
                    continue

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise ProgressOSClientError("ProgressOS menolak request bot.") from exc

                return ProgressOSActionResponse.model_validate(response.json())

            raise ProgressOSTransientError(
                "ProgressOS belum bisa dihubungi. Coba lagi sebentar."
            ) from last_error

    def build_quick_capture_request(
        self, request: ProgressOSActionRequest
    ) -> ProgressOSQuickCaptureRequest:
        action = request.parsed_action
        if action.intent != "create_task" or not isinstance(action.payload, CreateTaskPayload):
            raise ProgressOSClientError("Action belum didukung oleh quick capture.")

        notes = self._build_task_notes(request)
        return ProgressOSQuickCaptureRequest(
            type="task",
            title=action.payload.title,
            notes=notes,
            date=action.payload.due_date,
        )

    @staticmethod
    def _build_task_notes(request: ProgressOSActionRequest) -> str:
        payload = request.parsed_action.payload
        description = payload.description if isinstance(payload, CreateTaskPayload) else None
        parts = [
            f"Source: {request.source}",
            f"Source user: {request.source_user_id}",
            f"Source chat: {request.source_chat_id}",
            f"Original message: {request.original_text}",
        ]
        if description:
            parts.append(f"Description: {description}")
        return "\n".join(parts)

    @staticmethod
    def _new_idempotency_key() -> str:
        return str(uuid4())
