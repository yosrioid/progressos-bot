from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from progressos_bot.channels.base import ConfirmationRequest
from progressos_bot.channels.cli.adapter import CliChannelAdapter, CliDelivery
from progressos_bot.channels.cli.guided import CliGuidedCaptureForm
from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.core.guided_capture import GuidedCaptureChannelFlow
from progressos_bot.pending import InMemoryPendingActionStore
from progressos_bot.schemas import (
    CreateTaskPayload,
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


def test_cli_guided_capture_form_renders_field_prompts() -> None:
    form = CliGuidedCaptureForm.for_intent("create_task")

    assert form.prompt_lines() == [
        "Guided capture: create_task (create)",
        "- title: Title [text required]",
        "- description: Description [text optional]",
        "- due_date: Due date [date optional]",
        "- priority: Priority [priority required options=low,medium,high,urgent]",
    ]


def test_cli_guided_capture_form_builds_strict_guided_draft() -> None:
    form = CliGuidedCaptureForm.for_intent("create_task")

    draft = form.build_draft(
        {
            "title": "Review CLI guided flow",
            "description": "Pastikan form CLI memakai guided draft.",
            "due_date": "2026-06-26",
            "priority": "high",
        }
    )
    action = draft.to_parsed_action()

    assert action.intent == "create_task"
    assert isinstance(action.payload, CreateTaskPayload)
    assert action.payload.title == "Review CLI guided flow"
    assert action.payload.priority == "high"
    assert draft.user_confirmation_text == "Konfirmasi create_task Review CLI guided flow?"
    assert draft.original_text == "guided:create_task:create"


def test_cli_guided_capture_form_rejects_invalid_values() -> None:
    form = CliGuidedCaptureForm.for_intent("create_task")

    with pytest.raises(ValidationError):
        form.build_draft(
            {
                "title": "Review CLI guided flow",
                "description": None,
                "due_date": None,
                "priority": "critical",
            }
        )


@pytest.mark.asyncio
async def test_cli_guided_form_can_request_confirmation_without_progressos_submit() -> None:
    adapter = CliChannelAdapter()
    message = adapter.build_message(text="guided capture", user_id="admin-1")
    form = CliGuidedCaptureForm.for_intent("create_task")
    draft = form.build_draft(
        {
            "title": "Review CLI guided flow",
            "description": None,
            "due_date": None,
            "priority": "medium",
        }
    )
    progressos = FakeProgressOS()
    flow = CaptureFlow(
        parser=FakeParser(action=draft.to_parsed_action()),
        progressos=progressos,
        pending=InMemoryPendingActionStore(ttl_seconds=60),
    )
    guided_flow = GuidedCaptureChannelFlow(capture_flow=flow, channel=adapter)

    result = await guided_flow.request_confirmation(message=message, draft=draft)

    assert result.status == "confirmation_required"
    assert len(adapter.confirmation_requests) == 1
    assert "Review CLI guided flow" in adapter.confirmation_requests[0].prompt_text
    assert progressos.submitted_requests == []
