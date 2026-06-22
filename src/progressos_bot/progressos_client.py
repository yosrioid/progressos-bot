from collections.abc import Callable
from uuid import uuid4

import httpx

from progressos_bot.schemas import (
    CaptureLearningPayload,
    CreateBlockerPayload,
    CreateTaskPayload,
    LogDailyProgressPayload,
    LogWorkPayload,
    ProgressOSActionRequest,
    ProgressOSActionResponse,
    ProgressOSDashboardResponse,
    ProgressOSKanbanResponse,
    ProgressOSLearningStatsResponse,
    ProgressOSOverdueResponse,
    ProgressOSQuickCaptureRequest,
    ProgressOSSearchResponse,
    ProgressOSStandupResponse,
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

    async def get_standup(self) -> ProgressOSStandupResponse:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            try:
                response = await client.get(
                    f"{self._base_url}/api/v1/standup",
                    headers=self._headers,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise ProgressOSTransientError(
                    "ProgressOS belum bisa dihubungi. Coba lagi sebentar."
                ) from exc

            if response.status_code in {401, 403}:
                raise ProgressOSClientError("ProgressOS menolak akses standup.")

            if response.status_code >= 500:
                raise ProgressOSTransientError(
                    "ProgressOS sedang bermasalah. Coba lagi sebentar."
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ProgressOSClientError("ProgressOS menolak request standup.") from exc

            return ProgressOSStandupResponse.model_validate(response.json())

    async def get_dashboard(self) -> ProgressOSDashboardResponse:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            try:
                response = await client.get(
                    f"{self._base_url}/api/v1/dashboard",
                    headers=self._headers,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise ProgressOSTransientError(
                    "ProgressOS belum bisa dihubungi. Coba lagi sebentar."
                ) from exc

            if response.status_code in {401, 403}:
                raise ProgressOSClientError("ProgressOS menolak akses dashboard.")

            if response.status_code >= 500:
                raise ProgressOSTransientError(
                    "ProgressOS sedang bermasalah. Coba lagi sebentar."
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ProgressOSClientError("ProgressOS menolak request dashboard.") from exc

            return ProgressOSDashboardResponse.model_validate(response.json())

    async def search(self, query: str) -> ProgressOSSearchResponse:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            try:
                response = await client.get(
                    f"{self._base_url}/api/v1/search",
                    headers=self._headers,
                    params={"q": query},
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise ProgressOSTransientError(
                    "ProgressOS belum bisa dihubungi. Coba lagi sebentar."
                ) from exc

            if response.status_code in {401, 403}:
                raise ProgressOSClientError("ProgressOS menolak akses pencarian.")

            if response.status_code >= 500:
                raise ProgressOSTransientError(
                    "ProgressOS sedang bermasalah. Coba lagi sebentar."
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ProgressOSClientError("ProgressOS menolak request pencarian.") from exc

            return ProgressOSSearchResponse.model_validate(response.json())

    async def get_overdue(self) -> ProgressOSOverdueResponse:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            try:
                response = await client.get(
                    f"{self._base_url}/api/v1/tasks/overdue",
                    headers=self._headers,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise ProgressOSTransientError(
                    "ProgressOS belum bisa dihubungi. Coba lagi sebentar."
                ) from exc

            if response.status_code in {401, 403}:
                raise ProgressOSClientError("ProgressOS menolak akses task overdue.")

            if response.status_code >= 500:
                raise ProgressOSTransientError(
                    "ProgressOS sedang bermasalah. Coba lagi sebentar."
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ProgressOSClientError("ProgressOS menolak request task overdue.") from exc

            return ProgressOSOverdueResponse.model_validate(response.json())

    async def get_kanban(self) -> ProgressOSKanbanResponse:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            try:
                response = await client.get(
                    f"{self._base_url}/api/v1/tasks/kanban",
                    headers=self._headers,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise ProgressOSTransientError(
                    "ProgressOS belum bisa dihubungi. Coba lagi sebentar."
                ) from exc

            if response.status_code in {401, 403}:
                raise ProgressOSClientError("ProgressOS menolak akses kanban.")

            if response.status_code >= 500:
                raise ProgressOSTransientError(
                    "ProgressOS sedang bermasalah. Coba lagi sebentar."
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ProgressOSClientError("ProgressOS menolak request kanban.") from exc

            return ProgressOSKanbanResponse.model_validate(response.json())

    async def get_learning_stats(self) -> ProgressOSLearningStatsResponse:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            try:
                response = await client.get(
                    f"{self._base_url}/api/v1/learning/stats",
                    headers=self._headers,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise ProgressOSTransientError(
                    "ProgressOS belum bisa dihubungi. Coba lagi sebentar."
                ) from exc

            if response.status_code in {401, 403}:
                raise ProgressOSClientError("ProgressOS menolak akses learning stats.")

            if response.status_code >= 500:
                raise ProgressOSTransientError(
                    "ProgressOS sedang bermasalah. Coba lagi sebentar."
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ProgressOSClientError("ProgressOS menolak request learning stats.") from exc

            return ProgressOSLearningStatsResponse.model_validate(response.json())

    def build_quick_capture_request(
        self, request: ProgressOSActionRequest
    ) -> ProgressOSQuickCaptureRequest:
        action = request.parsed_action
        if action.intent == "create_task" and isinstance(action.payload, CreateTaskPayload):
            notes = self._build_notes(request, description=action.payload.description)
            return ProgressOSQuickCaptureRequest(
                type="task",
                title=action.payload.title,
                notes=notes,
                date=action.payload.due_date,
            )

        if action.intent == "create_blocker" and isinstance(action.payload, CreateBlockerPayload):
            notes = self._build_notes(
                request,
                description=action.payload.description,
                extra_parts=[f"Severity: {action.payload.severity}"],
            )
            return ProgressOSQuickCaptureRequest(
                type="blocker",
                title=action.payload.title,
                notes=notes,
            )

        if action.intent == "log_work" and isinstance(action.payload, LogWorkPayload):
            notes = self._build_notes(request, description=action.payload.description)
            return ProgressOSQuickCaptureRequest(
                type="work_log",
                title=action.payload.title,
                project_name=action.payload.project_name,
                notes=notes,
                date=action.payload.date,
                duration_minutes=action.payload.duration_minutes,
            )

        if action.intent == "log_daily_progress" and isinstance(
            action.payload, LogDailyProgressPayload
        ):
            notes = self._build_notes(request, description=action.payload.description)
            return ProgressOSQuickCaptureRequest(
                type="daily_progress",
                title=action.payload.title,
                project_name=action.payload.project_name,
                notes=notes,
                date=action.payload.date,
            )

        if action.intent == "capture_learning" and isinstance(
            action.payload, CaptureLearningPayload
        ):
            notes = self._build_notes(request, description=action.payload.description)
            return ProgressOSQuickCaptureRequest(
                type="learning",
                title=action.payload.title,
                project_name=action.payload.project_name,
                notes=notes,
                date=action.payload.date,
            )

        raise ProgressOSClientError("Action belum didukung oleh quick capture.")

    @staticmethod
    def _build_notes(
        request: ProgressOSActionRequest,
        *,
        description: str | None,
        extra_parts: list[str] | None = None,
    ) -> str:
        parts = [
            f"Source: {request.source}",
            f"Source user: {request.source_user_id}",
            f"Source chat: {request.source_chat_id}",
            f"Original message: {request.original_text}",
        ]
        if request.progressos_user_id:
            parts.append(f"ProgressOS user: {request.progressos_user_id}")
        if description:
            parts.append(f"Description: {description}")
        if extra_parts:
            parts.extend(extra_parts)
        return "\n".join(parts)

    @staticmethod
    def _new_idempotency_key() -> str:
        return str(uuid4())
