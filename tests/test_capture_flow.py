from dataclasses import dataclass, field

import pytest

from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.pending import InMemoryPendingActionStore
from progressos_bot.schemas import (
    ParsedAction,
    ProgressOSActionRequest,
    ProgressOSActionResponse,
)


def make_action(intent: str = "create_task") -> ParsedAction:
    if intent == "unsupported":
        return ParsedAction.model_validate(
            {
                "intent": "unsupported",
                "confidence": 0.91,
                "language": "id",
                "payload": {"reason": "Tidak didukung"},
                "user_confirmation_text": "Input ini belum didukung.",
            }
        )

    return ParsedAction.model_validate(
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


@dataclass
class FakeParser:
    action: ParsedAction
    parsed_messages: list[str] = field(default_factory=list)

    async def parse(self, message: str) -> ParsedAction:
        self.parsed_messages.append(message)
        return self.action


@dataclass
class FakeProgressOS:
    submitted_requests: list[ProgressOSActionRequest] = field(default_factory=list)

    async def submit_action(self, request: ProgressOSActionRequest) -> ProgressOSActionResponse:
        self.submitted_requests.append(request)
        return ProgressOSActionResponse(message="Capture tersimpan.", record_path="/tasks/1")


def make_flow(
    *,
    action: ParsedAction | None = None,
    progressos: FakeProgressOS | None = None,
) -> tuple[CaptureFlow, FakeParser, FakeProgressOS]:
    parser = FakeParser(action=action or make_action())
    client = progressos or FakeProgressOS()
    flow = CaptureFlow(
        parser=parser,
        progressos=client,
        pending=InMemoryPendingActionStore(ttl_seconds=60),
        correlation_id_factory=lambda: "corr-capture",
    )
    return flow, parser, client


@pytest.mark.asyncio
async def test_begin_capture_stores_supported_action_without_telegram_classes() -> None:
    flow, parser, _client = make_flow()

    result = await flow.begin_capture(
        user_key="telegram:123",
        original_text="buat task follow up invoice client A",
    )

    assert result.status == "confirmation_required"
    assert result.user_message == "Buat task Follow up invoice client A?"
    assert result.correlation_id == "corr-capture"
    assert parser.parsed_messages == ["buat task follow up invoice client A"]


@pytest.mark.asyncio
async def test_begin_capture_returns_unsupported_without_pending_submit() -> None:
    flow, _parser, client = make_flow(action=make_action("unsupported"))

    result = await flow.begin_capture(
        user_key="telegram:123",
        original_text="hapus semua task",
    )
    submitted = await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert result.status == "unsupported"
    assert result.user_message == "Input ini belum didukung."
    assert submitted.submitted is False
    assert submitted.user_message == "Tidak ada draft aktif atau draft sudah kedaluwarsa."
    assert client.submitted_requests == []


@pytest.mark.asyncio
async def test_submit_confirmed_capture_sends_pending_action_to_progressos() -> None:
    flow, _parser, client = make_flow()
    await flow.begin_capture(
        user_key="telegram:123",
        original_text="buat task follow up invoice client A",
    )

    result = await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert result.submitted is True
    assert result.correlation_id == "corr-capture"
    assert result.user_message == "Capture tersimpan.\nLokasi: /tasks/1"
    assert len(client.submitted_requests) == 1
    request = client.submitted_requests[0]
    assert request.source == "telegram"
    assert request.source_user_id == "123"
    assert request.source_chat_id == "456"
    assert request.progressos_user_id == "77"
    assert request.original_text == "buat task follow up invoice client A"


@pytest.mark.asyncio
async def test_cancel_capture_discards_pending_action() -> None:
    flow, _parser, client = make_flow()
    await flow.begin_capture(
        user_key="telegram:123",
        original_text="buat task follow up invoice client A",
    )

    flow.cancel_capture(user_key="telegram:123")
    result = await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert result.submitted is False
    assert result.user_message == "Tidak ada draft aktif atau draft sudah kedaluwarsa."
    assert client.submitted_requests == []
