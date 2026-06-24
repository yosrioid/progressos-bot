from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from progressos_bot.channels.cli.adapter import CliChannelAdapter
from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.core.guided_capture import (
    GuidedCaptureChannelFlow,
    GuidedCaptureDraft,
    guided_capture_fields,
)
from progressos_bot.pending import InMemoryPendingActionStore
from progressos_bot.schemas import (
    CreateTaskPayload,
    ParsedAction,
    ProgressOSActionRequest,
    ProgressOSActionResponse,
)


def make_guided_task() -> GuidedCaptureDraft:
    return GuidedCaptureDraft.model_validate(
        {
            "intent": "create_task",
            "language": "id",
            "payload": {
                "title": "Review guided capture contract",
                "description": "Pastikan guided capture memakai ParsedAction.",
                "due_date": "2026-06-25",
                "priority": "high",
            },
            "user_confirmation_text": "Buat task Review guided capture contract?",
            "original_text": "guided:create_task",
        }
    )


@dataclass
class StaticGuidedParser:
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


def test_guided_capture_draft_builds_strict_parsed_action() -> None:
    draft = make_guided_task()

    action = draft.to_parsed_action()

    assert action.intent == "create_task"
    assert action.confidence == 1.0
    assert action.language == "id"
    assert isinstance(action.payload, CreateTaskPayload)
    assert action.payload.title == "Review guided capture contract"
    assert action.payload.priority == "high"
    assert action.user_confirmation_text == "Buat task Review guided capture contract?"


def test_guided_capture_draft_rejects_unknown_fields() -> None:
    payload = make_guided_task().model_dump(mode="json")
    payload["progressos_path"] = "/api/v1/admin/users"

    with pytest.raises(ValidationError):
        GuidedCaptureDraft.model_validate(payload)


def test_guided_capture_draft_rejects_wrong_payload_for_intent() -> None:
    with pytest.raises(ValidationError):
        GuidedCaptureDraft.model_validate(
            {
                "intent": "log_work",
                "language": "id",
                "payload": {
                    "title": "Review guided capture contract",
                    "description": None,
                    "due_date": None,
                    "priority": "high",
                },
                "user_confirmation_text": "Catat work log Review guided capture contract?",
            }
        )


def test_guided_capture_draft_builds_preview_lines() -> None:
    draft = make_guided_task()

    assert draft.preview_lines() == [
        "Intent: create_task",
        "Title: Review guided capture contract",
        "Description: Pastikan guided capture memakai ParsedAction.",
        "Due Date: 2026-06-25",
        "Priority: high",
    ]


def test_guided_capture_draft_apply_payload_edit_revalidates_draft() -> None:
    draft = make_guided_task()

    edited = draft.apply_payload_edit(
        {"priority": "urgent", "due_date": "2026-06-26"},
        user_confirmation_text="Buat task Review guided capture contract prioritas urgent?",
    )
    action = edited.to_parsed_action()

    assert isinstance(action.payload, CreateTaskPayload)
    assert action.payload.priority == "urgent"
    assert action.payload.due_date is not None
    assert action.payload.due_date.isoformat() == "2026-06-26"
    assert (
        action.user_confirmation_text
        == "Buat task Review guided capture contract prioritas urgent?"
    )


def test_guided_capture_draft_apply_payload_edit_rejects_invalid_value() -> None:
    draft = make_guided_task()

    with pytest.raises(ValidationError):
        draft.apply_payload_edit({"priority": "critical"})


def test_guided_capture_fields_expose_task_date_and_priority_pickers() -> None:
    fields = {field.key: field for field in guided_capture_fields("create_task")}

    assert fields["due_date"].field_type == "date"
    assert fields["due_date"].required is False
    assert fields["priority"].field_type == "priority"
    assert fields["priority"].options == ("low", "medium", "high", "urgent")


def test_guided_capture_fields_expose_blocker_severity_picker() -> None:
    fields = {field.key: field for field in guided_capture_fields("create_blocker")}

    assert fields["severity"].field_type == "priority"
    assert fields["severity"].label == "Severity"
    assert fields["severity"].options == ("low", "medium", "high", "urgent")


def test_guided_capture_fields_expose_work_date_duration_and_project_inputs() -> None:
    fields = {field.key: field for field in guided_capture_fields("log_work")}

    assert fields["date"].field_type == "date"
    assert fields["date"].required is False
    assert fields["duration_minutes"].field_type == "duration_minutes"
    assert fields["project_name"].field_type == "text"
    assert fields["project_name"].required is False


@pytest.mark.asyncio
async def test_guided_capture_reuses_capture_flow_confirmation_gate() -> None:
    guided = make_guided_task()
    progressos = FakeProgressOS()
    parser = StaticGuidedParser(action=guided.to_parsed_action())
    flow = CaptureFlow(
        parser=parser,
        progressos=progressos,
        pending=InMemoryPendingActionStore(ttl_seconds=60),
    )

    draft = await flow.begin_capture(
        user_key="telegram:123",
        original_text=guided.original_text,
    )

    assert draft.status == "confirmation_required"
    assert parser.parsed_messages == ["guided:create_task"]
    assert progressos.submitted_requests == []

    result = await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert result.submitted is True
    assert len(progressos.submitted_requests) == 1
    assert progressos.submitted_requests[0].parsed_action == guided.to_parsed_action()


@pytest.mark.asyncio
async def test_guided_capture_edit_still_requires_confirmation_before_submit() -> None:
    guided = make_guided_task().apply_payload_edit({"priority": "urgent"})
    progressos = FakeProgressOS()
    parser = StaticGuidedParser(action=guided.to_parsed_action())
    flow = CaptureFlow(
        parser=parser,
        progressos=progressos,
        pending=InMemoryPendingActionStore(ttl_seconds=60),
    )

    draft = await flow.begin_capture(
        user_key="telegram:123",
        original_text=guided.original_text,
    )

    assert draft.status == "confirmation_required"
    assert progressos.submitted_requests == []

    result = await flow.submit_confirmed_capture(
        user_key="telegram:123",
        source_user_id="123",
        source_chat_id="456",
        progressos_user_id="77",
    )

    assert result.submitted is True
    assert len(progressos.submitted_requests) == 1
    submitted_action = progressos.submitted_requests[0].parsed_action
    assert isinstance(submitted_action.payload, CreateTaskPayload)
    assert submitted_action.payload.priority == "urgent"


@pytest.mark.asyncio
async def test_guided_channel_flow_requests_confirmation_with_preview() -> None:
    adapter = CliChannelAdapter()
    message = adapter.build_message(text="guided capture", user_id="admin-1")
    guided = make_guided_task()
    progressos = FakeProgressOS()
    capture_flow = CaptureFlow(
        parser=StaticGuidedParser(action=guided.to_parsed_action()),
        progressos=progressos,
        pending=InMemoryPendingActionStore(ttl_seconds=60),
        correlation_id_factory=lambda: "corr-guided",
    )
    guided_flow = GuidedCaptureChannelFlow(
        capture_flow=capture_flow,
        channel=adapter,
    )

    result = await guided_flow.request_confirmation(message=message, draft=guided)

    assert result.status == "confirmation_required"
    assert adapter.sent_texts == []
    assert len(adapter.confirmation_requests) == 1
    request = adapter.confirmation_requests[0]
    assert request.request_id == "corr-guided"
    assert request.conversation_id == "local-cli"
    assert request.user.channel_user_id == "admin-1"
    assert "Buat task Review guided capture contract?" in request.prompt_text
    assert "Priority: high" in request.prompt_text
    assert progressos.submitted_requests == []


@pytest.mark.asyncio
async def test_guided_channel_flow_submit_confirmed_uses_channel_metadata() -> None:
    adapter = CliChannelAdapter()
    message = adapter.build_message(text="guided capture", user_id="admin-1")
    guided = make_guided_task()
    progressos = FakeProgressOS()
    capture_flow = CaptureFlow(
        parser=StaticGuidedParser(action=guided.to_parsed_action()),
        progressos=progressos,
        pending=InMemoryPendingActionStore(ttl_seconds=60),
    )
    guided_flow = GuidedCaptureChannelFlow(
        capture_flow=capture_flow,
        channel=adapter,
    )

    await guided_flow.request_confirmation(message=message, draft=guided)
    result = await guided_flow.submit_confirmed(
        message=message,
        progressos_user_id="77",
    )

    assert result.submitted is True
    assert len(progressos.submitted_requests) == 1
    request = progressos.submitted_requests[0]
    assert request.source == "cli"
    assert request.source_user_id == "admin-1"
    assert request.source_chat_id == "local-cli"
    assert request.progressos_user_id == "77"
    assert request.parsed_action == guided.to_parsed_action()


@pytest.mark.asyncio
async def test_guided_channel_flow_rejects_disabled_intent_without_confirmation() -> None:
    adapter = CliChannelAdapter()
    message = adapter.build_message(text="guided capture", user_id="admin-1")
    guided = make_guided_task()
    progressos = FakeProgressOS()
    capture_flow = CaptureFlow(
        parser=StaticGuidedParser(action=guided.to_parsed_action()),
        progressos=progressos,
        pending=InMemoryPendingActionStore(ttl_seconds=60),
        enabled_intents={"log_work"},
    )
    guided_flow = GuidedCaptureChannelFlow(
        capture_flow=capture_flow,
        channel=adapter,
    )

    result = await guided_flow.request_confirmation(message=message, draft=guided)

    assert result.status == "unsupported"
    assert adapter.confirmation_requests == []
    assert len(adapter.sent_texts) == 1
    assert adapter.sent_texts[0].text == "Intent create_task sedang dinonaktifkan admin."
    assert progressos.submitted_requests == []
