import json

import httpx
import pytest

from progressos_bot.progressos_client import (
    ProgressOSClient,
    ProgressOSClientError,
    ProgressOSTransientError,
    ProgressOSValidationError,
)
from progressos_bot.schemas import ParsedAction, ProgressOSActionRequest


def make_action_request() -> ProgressOSActionRequest:
    action = ParsedAction.model_validate(
        {
            "intent": "create_task",
            "confidence": 0.91,
            "language": "id",
            "payload": {
                "title": "Follow up invoice client A",
                "description": "Kirim invoice ulang",
                "due_date": "2026-06-21",
                "priority": "high",
            },
            "user_confirmation_text": "Buat task Follow up invoice client A?",
        }
    )
    return ProgressOSActionRequest(
        source_user_id="123",
        source_chat_id="456",
        original_text="buat task follow up invoice client A besok",
        parsed_action=action,
    )


def make_blocker_action_request() -> ProgressOSActionRequest:
    action = ParsedAction.model_validate(
        {
            "intent": "create_blocker",
            "confidence": 0.89,
            "language": "id",
            "payload": {
                "title": "Blocked by missing API token",
                "description": "Need ProgressOS token from admin",
                "severity": "high",
            },
            "user_confirmation_text": "Catat blocker missing API token?",
        }
    )
    return ProgressOSActionRequest(
        source_user_id="123",
        source_chat_id="456",
        original_text="catat blocker token API belum ada",
        parsed_action=action,
    )


def make_work_log_action_request() -> ProgressOSActionRequest:
    action = ParsedAction.model_validate(
        {
            "intent": "log_work",
            "confidence": 0.9,
            "language": "id",
            "payload": {
                "title": "Implement Telegram webhook",
                "description": "Finished webhook server draft",
                "date": "2026-06-22",
                "duration_minutes": 90,
                "project_name": "ProgressOS",
            },
            "user_confirmation_text": "Catat work log Implement Telegram webhook?",
        }
    )
    return ProgressOSActionRequest(
        source_user_id="123",
        source_chat_id="456",
        original_text="catat kerja 90 menit implement webhook Telegram",
        parsed_action=action,
    )


def make_daily_progress_action_request() -> ProgressOSActionRequest:
    action = ParsedAction.model_validate(
        {
            "intent": "log_daily_progress",
            "confidence": 0.9,
            "language": "id",
            "payload": {
                "title": "Backend integration progress",
                "description": "Quick-capture client and Telegram confirmation are done",
                "date": "2026-06-22",
                "project_name": "ProgressOS",
            },
            "user_confirmation_text": "Catat daily progress Backend integration progress?",
        }
    )
    return ProgressOSActionRequest(
        source_user_id="123",
        source_chat_id="456",
        original_text="catat daily progress integrasi backend selesai",
        parsed_action=action,
    )


def make_learning_action_request() -> ProgressOSActionRequest:
    action = ParsedAction.model_validate(
        {
            "intent": "capture_learning",
            "confidence": 0.9,
            "language": "id",
            "payload": {
                "title": "Telegram webhook retry strategy",
                "description": "Use idempotency key when retrying quick-capture writes",
                "date": "2026-06-22",
                "project_name": "ProgressOS",
            },
            "user_confirmation_text": "Catat learning Telegram webhook retry strategy?",
        }
    )
    return ProgressOSActionRequest(
        source_user_id="123",
        source_chat_id="456",
        original_text="catat learning retry webhook pakai idempotency key",
        parsed_action=action,
    )


@pytest.mark.asyncio
async def test_submit_action_posts_quick_capture_payload_with_idempotency_key() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(
            200,
            json={
                "message": "Captured.",
                "record": {"id": 42, "title": "Follow up invoice client A"},
                "record_path": "/tasks/42",
            },
        )

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        idempotency_key_factory=lambda: "fixed-key",
        transport=httpx.MockTransport(handler),
    )

    response = await client.submit_action(make_action_request())

    assert response.message == "Captured."
    assert response.record == {"id": 42, "title": "Follow up invoice client A"}
    assert response.record_path == "/tasks/42"
    assert response.to_user_message() == "Captured.\nLokasi: /tasks/42"
    assert len(seen_requests) == 1
    request = seen_requests[0]
    assert request.headers["Authorization"] == "Bearer secret-token"
    assert request.headers["Idempotency-Key"] == "fixed-key"
    assert request.url.path == "/api/v1/quick-capture"
    payload = json.loads(request.content)
    assert payload["type"] == "task"
    assert payload["title"] == "Follow up invoice client A"
    assert payload["date"] == "2026-06-21"
    assert "Original message: buat task follow up invoice client A besok" in payload["notes"]
    assert request.headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_submit_action_posts_blocker_quick_capture_payload() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json={"message": "Blocker captured."})

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        idempotency_key_factory=lambda: "fixed-key",
        transport=httpx.MockTransport(handler),
    )

    response = await client.submit_action(make_blocker_action_request())

    assert response.message == "Blocker captured."
    assert len(seen_requests) == 1
    payload = json.loads(seen_requests[0].content)
    assert payload["type"] == "blocker"
    assert payload["title"] == "Blocked by missing API token"
    assert "Original message: catat blocker token API belum ada" in payload["notes"]
    assert "Description: Need ProgressOS token from admin" in payload["notes"]
    assert "Severity: high" in payload["notes"]
    assert "date" not in payload


@pytest.mark.asyncio
async def test_submit_action_posts_work_log_quick_capture_payload() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json={"message": "Work log captured."})

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        idempotency_key_factory=lambda: "fixed-key",
        transport=httpx.MockTransport(handler),
    )

    response = await client.submit_action(make_work_log_action_request())

    assert response.message == "Work log captured."
    assert len(seen_requests) == 1
    payload = json.loads(seen_requests[0].content)
    assert payload["type"] == "work_log"
    assert payload["title"] == "Implement Telegram webhook"
    assert payload["project_name"] == "ProgressOS"
    assert payload["date"] == "2026-06-22"
    assert payload["duration_minutes"] == 90
    assert "Original message: catat kerja 90 menit implement webhook Telegram" in payload["notes"]
    assert "Description: Finished webhook server draft" in payload["notes"]


@pytest.mark.asyncio
async def test_submit_action_posts_daily_progress_quick_capture_payload() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json={"message": "Daily progress captured."})

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        idempotency_key_factory=lambda: "fixed-key",
        transport=httpx.MockTransport(handler),
    )

    response = await client.submit_action(make_daily_progress_action_request())

    assert response.message == "Daily progress captured."
    assert len(seen_requests) == 1
    payload = json.loads(seen_requests[0].content)
    assert payload["type"] == "daily_progress"
    assert payload["title"] == "Backend integration progress"
    assert payload["project_name"] == "ProgressOS"
    assert payload["date"] == "2026-06-22"
    assert "Original message: catat daily progress integrasi backend selesai" in payload["notes"]
    assert "Description: Quick-capture client and Telegram confirmation are done" in payload[
        "notes"
    ]


@pytest.mark.asyncio
async def test_submit_action_posts_learning_quick_capture_payload() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json={"message": "Learning captured."})

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        idempotency_key_factory=lambda: "fixed-key",
        transport=httpx.MockTransport(handler),
    )

    response = await client.submit_action(make_learning_action_request())

    assert response.message == "Learning captured."
    assert len(seen_requests) == 1
    payload = json.loads(seen_requests[0].content)
    assert payload["type"] == "learning"
    assert payload["title"] == "Telegram webhook retry strategy"
    assert payload["project_name"] == "ProgressOS"
    assert payload["date"] == "2026-06-22"
    assert "Original message: catat learning retry webhook pakai idempotency key" in payload[
        "notes"
    ]
    assert "Description: Use idempotency key when retrying quick-capture writes" in payload[
        "notes"
    ]


@pytest.mark.asyncio
async def test_submit_action_accepts_success_response_without_optional_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Idempotency-Key"] == "fixed-key"
        return httpx.Response(200, json={})

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        idempotency_key_factory=lambda: "fixed-key",
        transport=httpx.MockTransport(handler),
    )

    response = await client.submit_action(make_action_request())

    assert response.message is None
    assert response.record is None
    assert response.record_path is None
    assert response.to_user_message() == "Capture tersimpan."


def test_build_quick_capture_request_maps_confirmed_task() -> None:
    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
    )

    quick_capture = client.build_quick_capture_request(make_action_request())

    assert quick_capture.type == "task"
    assert quick_capture.title == "Follow up invoice client A"
    assert quick_capture.date is not None
    assert quick_capture.notes is not None
    assert "Original message: buat task follow up invoice client A besok" in quick_capture.notes
    assert "Description: Kirim invoice ulang" in quick_capture.notes


def test_build_quick_capture_request_maps_confirmed_blocker() -> None:
    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
    )

    quick_capture = client.build_quick_capture_request(make_blocker_action_request())

    assert quick_capture.type == "blocker"
    assert quick_capture.title == "Blocked by missing API token"
    assert quick_capture.date is None
    assert quick_capture.notes is not None
    assert "Description: Need ProgressOS token from admin" in quick_capture.notes
    assert "Severity: high" in quick_capture.notes


def test_build_quick_capture_request_maps_confirmed_work_log() -> None:
    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
    )

    quick_capture = client.build_quick_capture_request(make_work_log_action_request())

    assert quick_capture.type == "work_log"
    assert quick_capture.title == "Implement Telegram webhook"
    assert quick_capture.project_name == "ProgressOS"
    assert quick_capture.date is not None
    assert quick_capture.duration_minutes == 90
    assert quick_capture.notes is not None
    assert "Description: Finished webhook server draft" in quick_capture.notes


def test_build_quick_capture_request_maps_confirmed_daily_progress() -> None:
    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
    )

    quick_capture = client.build_quick_capture_request(make_daily_progress_action_request())

    assert quick_capture.type == "daily_progress"
    assert quick_capture.title == "Backend integration progress"
    assert quick_capture.project_name == "ProgressOS"
    assert quick_capture.date is not None
    assert quick_capture.duration_minutes is None
    assert quick_capture.notes is not None
    assert "Description: Quick-capture client and Telegram confirmation are done" in (
        quick_capture.notes
    )


def test_build_quick_capture_request_maps_confirmed_learning() -> None:
    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
    )

    quick_capture = client.build_quick_capture_request(make_learning_action_request())

    assert quick_capture.type == "learning"
    assert quick_capture.title == "Telegram webhook retry strategy"
    assert quick_capture.project_name == "ProgressOS"
    assert quick_capture.date is not None
    assert quick_capture.duration_minutes is None
    assert quick_capture.notes is not None
    assert "Description: Use idempotency key when retrying quick-capture writes" in (
        quick_capture.notes
    )


@pytest.mark.asyncio
async def test_submit_action_raises_validation_error_for_laravel_422() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Idempotency-Key"] == "fixed-key"
        return httpx.Response(
            422,
            json={
                "message": "Validation failed",
                "errors": {"title": ["The title field is required."]},
            },
        )

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        idempotency_key_factory=lambda: "fixed-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProgressOSValidationError) as exc_info:
        await client.submit_action(make_action_request())

    assert exc_info.value.response.message == "Validation failed"
    assert exc_info.value.response.errors["title"] == ["The title field is required."]


@pytest.mark.asyncio
async def test_submit_action_retries_transient_server_errors_with_same_idempotency_key() -> None:
    seen_keys: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_keys.append(request.headers["Idempotency-Key"])
        if len(seen_keys) == 1:
            return httpx.Response(503, json={"message": "Temporary failure"})
        return httpx.Response(200, json={"message": "Captured."})

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        idempotency_key_factory=lambda: "fixed-key",
        max_attempts=2,
        transport=httpx.MockTransport(handler),
    )

    response = await client.submit_action(make_action_request())

    assert response.message == "Captured."
    assert seen_keys == ["fixed-key", "fixed-key"]


@pytest.mark.asyncio
async def test_submit_action_raises_transient_error_after_timeout_retries() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.TimeoutException("timeout", request=request)

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        idempotency_key_factory=lambda: "fixed-key",
        max_attempts=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProgressOSTransientError):
        await client.submit_action(make_action_request())

    assert attempts == 2


@pytest.mark.asyncio
async def test_get_standup_returns_concise_user_message() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(
            200,
            json={
                "message": "Standup hari ini",
                "items": [
                    {
                        "title": "Ship quick capture",
                        "project_name": "ProgressOS",
                        "status": "done",
                    },
                    {
                        "title": "Review webhook deployment",
                        "project_name": "ProgressOS",
                        "status": "next",
                    },
                ],
            },
        )

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    response = await client.get_standup()

    assert len(seen_requests) == 1
    request = seen_requests[0]
    assert request.method == "GET"
    assert request.url.path == "/api/v1/standup"
    assert request.headers["Authorization"] == "Bearer secret-token"
    assert response.to_user_message() == (
        "Standup hari ini\n"
        "1. Ship quick capture (ProgressOS, done)\n"
        "2. Review webhook deployment (ProgressOS, next)"
    )


@pytest.mark.asyncio
async def test_get_standup_handles_empty_state() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": []})

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    response = await client.get_standup()

    assert response.items == []
    assert response.to_user_message() == "Tidak ada item standup."


@pytest.mark.asyncio
async def test_get_standup_rejects_unauthorized_response_safely() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Forbidden details"})

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProgressOSClientError, match="menolak akses standup"):
        await client.get_standup()


@pytest.mark.asyncio
async def test_get_standup_raises_transient_error_for_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "Temporary failure"})

    client = ProgressOSClient(
        base_url="https://progressos.test",
        token="secret-token",
        endpoint="/api/v1/quick-capture",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProgressOSTransientError):
        await client.get_standup()
