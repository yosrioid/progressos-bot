from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.core.guided_capture import GuidedCaptureDraft
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
