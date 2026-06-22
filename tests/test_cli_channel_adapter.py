from dataclasses import dataclass, field

import pytest

from progressos_bot.channels.base import ConfirmationRequest
from progressos_bot.channels.cli.adapter import CliChannelAdapter, CliDelivery
from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.pending import InMemoryPendingActionStore
from progressos_bot.schemas import (
    ParsedAction,
    ProgressOSActionRequest,
    ProgressOSActionResponse,
)


def make_action() -> ParsedAction:
    return ParsedAction.model_validate(
        {
            "intent": "create_task",
            "confidence": 0.91,
            "language": "id",
            "payload": {
                "title": "Review CLI adapter",
                "description": "Pastikan adapter non-Telegram memakai core flow",
                "due_date": None,
                "priority": "medium",
            },
            "user_confirmation_text": "Buat task Review CLI adapter?",
        }
    )


@dataclass
class FakeParser:
    action: ParsedAction

    async def parse(self, message: str) -> ParsedAction:
        assert message == "buat task review CLI adapter"
        return self.action


@dataclass
class FakeProgressOS:
    submitted_requests: list[ProgressOSActionRequest] = field(default_factory=list)

    async def submit_action(self, request: ProgressOSActionRequest) -> ProgressOSActionResponse:
        self.submitted_requests.append(request)
        return ProgressOSActionResponse(message="Capture tersimpan.")


def test_cli_channel_adapter_builds_channel_neutral_message() -> None:
    adapter = CliChannelAdapter()

    message = adapter.build_message(
        text="buat task review CLI adapter",
        user_id="admin-1",
        conversation_id="cli-session",
        message_id="line-1",
    )

    assert message.channel == "cli"
    assert message.user.channel == "cli"
    assert message.user.channel_user_id == "admin-1"
    assert message.conversation_id == "cli-session"
    assert message.text == "buat task review CLI adapter"


@pytest.mark.asyncio
async def test_cli_channel_adapter_records_text_and_confirmation_requests() -> None:
    adapter = CliChannelAdapter()
    message = adapter.build_message(text="buat task review CLI adapter")
    request = ConfirmationRequest(
        request_id="request-1",
        conversation_id=message.conversation_id,
        user=message.user,
        prompt_text="Buat task Review CLI adapter?",
    )

    await adapter.send_text(conversation_id=message.conversation_id, text="Memproses input...")
    await adapter.request_confirmation(request)

    assert adapter.sent_texts == [
        CliDelivery(conversation_id="local-cli", text="Memproses input...")
    ]
    assert adapter.confirmation_requests == [request]


@pytest.mark.asyncio
async def test_cli_channel_can_reuse_capture_flow_without_telegram_classes() -> None:
    adapter = CliChannelAdapter()
    message = adapter.build_message(text="buat task review CLI adapter", user_id="admin-1")
    progressos = FakeProgressOS()
    flow = CaptureFlow(
        parser=FakeParser(action=make_action()),
        progressos=progressos,
        pending=InMemoryPendingActionStore(ttl_seconds=60),
    )

    draft = await flow.begin_capture(
        user_key=f"{message.user.channel}:{message.user.channel_user_id}",
        original_text=message.text,
    )
    await adapter.request_confirmation(
        ConfirmationRequest(
            request_id="request-1",
            conversation_id=message.conversation_id,
            user=message.user,
            prompt_text=draft.user_message,
        )
    )
    result = await flow.submit_confirmed_capture(
        user_key=f"{message.user.channel}:{message.user.channel_user_id}",
        source=message.channel,
        source_user_id=message.user.channel_user_id,
        source_chat_id=message.conversation_id,
        progressos_user_id="77",
    )

    assert draft.status == "confirmation_required"
    assert adapter.confirmation_requests[0].user.channel == "cli"
    assert result.submitted is True
    assert progressos.submitted_requests[0].source == "cli"
    assert progressos.submitted_requests[0].source_user_id == "admin-1"
