from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from progressos_bot.channels.base import ConfirmationRequest
from progressos_bot.channels.web.adapter import (
    WEB_CHAT_CHANNEL,
    WebChatChannelAdapter,
    WebChatDelivery,
    WebChatInboundMessage,
    WebChatSession,
)
from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.core.identity import CaptureIdentityService
from progressos_bot.core.read_commands import ReadCommandFlow
from progressos_bot.identity import ChannelUserIdentity
from progressos_bot.pending import InMemoryPendingActionStore
from progressos_bot.schemas import (
    ParsedAction,
    ProgressOSActionRequest,
    ProgressOSActionResponse,
    ProgressOSDashboardResponse,
)


def make_task_action() -> ParsedAction:
    return ParsedAction.model_validate(
        {
            "intent": "create_task",
            "confidence": 0.91,
            "language": "id",
            "payload": {
                "title": "Review web chat adapter",
                "description": "Pastikan adapter web memakai core flow",
                "due_date": None,
                "priority": "medium",
            },
            "user_confirmation_text": "Buat task Review web chat adapter?",
        }
    )


def make_log_work_action() -> ParsedAction:
    return ParsedAction.model_validate(
        {
            "intent": "log_work",
            "confidence": 0.91,
            "language": "id",
            "payload": {
                "title": "Implement web chat adapter",
                "description": "Menambah adapter channel kedua",
                "date": "2026-06-24",
                "duration_minutes": 90,
                "project_name": "ProgressOS Bot",
            },
            "user_confirmation_text": "Catat work Implement web chat adapter?",
        }
    )


@dataclass
class FakeParser:
    actions_by_message: dict[str, ParsedAction]

    async def parse(self, message: str) -> ParsedAction:
        return self.actions_by_message[message]


@dataclass
class FakeProgressOS:
    submitted_requests: list[ProgressOSActionRequest] = field(default_factory=list)

    async def submit_action(self, request: ProgressOSActionRequest) -> ProgressOSActionResponse:
        self.submitted_requests.append(request)
        return ProgressOSActionResponse(message="Capture tersimpan.")


@dataclass
class FakeAuthorizer:
    seen_identities: list[ChannelUserIdentity] = field(default_factory=list)

    def require_authorized(self, identity: ChannelUserIdentity) -> None:
        self.seen_identities.append(identity)


@dataclass
class FakeResolver:
    seen_identities: list[ChannelUserIdentity] = field(default_factory=list)

    def resolve(self, identity: ChannelUserIdentity) -> str:
        self.seen_identities.append(identity)
        return "77"


@dataclass
class FakeReadClient:
    calls: list[str] = field(default_factory=list)

    async def get_dashboard(self) -> ProgressOSDashboardResponse:
        self.calls.append("dashboard")
        return ProgressOSDashboardResponse(message="Dashboard siap")


def make_inbound_message(text: str, *, message_id: str = "msg-1") -> WebChatInboundMessage:
    return WebChatInboundMessage(
        message_id=message_id,
        session=WebChatSession(
            session_id="session-1",
            user_id="web-user-1",
            display_name="Ryo",
        ),
        text=text,
    )


def test_web_chat_adapter_builds_channel_neutral_message() -> None:
    adapter = WebChatChannelAdapter()

    message = adapter.build_message(make_inbound_message("buat task review web chat"))

    assert message.channel == WEB_CHAT_CHANNEL
    assert message.user.channel == WEB_CHAT_CHANNEL
    assert message.user.channel_user_id == "web-user-1"
    assert message.user.display_name == "Ryo"
    assert message.conversation_id == "session-1"
    assert message.text == "buat task review web chat"


def test_web_chat_contracts_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        WebChatInboundMessage.model_validate(
            {
                "message_id": "msg-1",
                "session": {
                    "session_id": "session-1",
                    "user_id": "web-user-1",
                },
                "text": "buat task",
                "unexpected": "value",
            }
        )


@pytest.mark.asyncio
async def test_web_chat_adapter_records_text_and_confirmation_deliveries() -> None:
    adapter = WebChatChannelAdapter()
    message = adapter.build_message(make_inbound_message("buat task review web chat"))
    request = ConfirmationRequest(
        request_id="request-1",
        conversation_id=message.conversation_id,
        user=message.user,
        prompt_text="Buat task Review web chat?",
    )

    await adapter.send_text(conversation_id=message.conversation_id, text="Memproses input...")
    await adapter.request_confirmation(request)

    assert adapter.deliveries == [
        WebChatDelivery(
            delivery_type="text",
            session_id="session-1",
            text="Memproses input...",
        ),
        WebChatDelivery(
            delivery_type="confirmation_request",
            session_id="session-1",
            text="Buat task Review web chat?",
            request_id="request-1",
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "action"),
    [
        ("buat task review web chat", make_task_action()),
        ("catat kerja implement web chat 90 menit", make_log_work_action()),
    ],
)
async def test_web_chat_can_reuse_capture_flow_for_supported_captures(
    text: str,
    action: ParsedAction,
) -> None:
    adapter = WebChatChannelAdapter()
    message = adapter.build_message(make_inbound_message(text))
    progressos = FakeProgressOS()
    flow = CaptureFlow(
        parser=FakeParser(actions_by_message={text: action}),
        progressos=progressos,
        pending=InMemoryPendingActionStore(ttl_seconds=60),
    )

    draft = await flow.begin_capture(
        user_key=f"{message.user.channel}:{message.user.channel_user_id}",
        original_text=message.text,
    )
    await adapter.request_confirmation(
        ConfirmationRequest(
            request_id=draft.correlation_id,
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
    assert result.submitted is True
    assert adapter.deliveries[0].delivery_type == "confirmation_request"
    assert progressos.submitted_requests[0].source == WEB_CHAT_CHANNEL
    assert progressos.submitted_requests[0].source_user_id == "web-user-1"
    assert progressos.submitted_requests[0].source_chat_id == "session-1"
    assert progressos.submitted_requests[0].parsed_action.intent == action.intent


@pytest.mark.asyncio
async def test_web_chat_read_command_uses_channel_identity_resolution_path() -> None:
    adapter = WebChatChannelAdapter()
    message = adapter.build_message(make_inbound_message("/dashboard"))
    authorizer = FakeAuthorizer()
    resolver = FakeResolver()
    identity_service = CaptureIdentityService(
        authorizer=authorizer,
        progressos_user_resolver=resolver,
    )
    channel_identity = ChannelUserIdentity(
        channel=message.user.channel,
        channel_user_id=message.user.channel_user_id,
    )
    resolved = identity_service.resolve_for_capture(channel_identity)
    read_client = FakeReadClient()
    read_flow = ReadCommandFlow(
        progressos=read_client,
        correlation_id_factory=lambda: "corr-web-read",
    )

    result = await read_flow.dashboard()
    await adapter.send_text(conversation_id=message.conversation_id, text=result.user_message)

    assert resolved.progressos_user_id == "77"
    assert authorizer.seen_identities == [channel_identity]
    assert resolver.seen_identities == [channel_identity]
    assert read_client.calls == ["dashboard"]
    assert adapter.deliveries == [
        WebChatDelivery(
            delivery_type="text",
            session_id="session-1",
            text="Dashboard siap",
        )
    ]
