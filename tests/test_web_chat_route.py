from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from progressos_bot.channels.web.route import WebChatHttpHandler, WebChatRoutedRequest
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
                "title": "Review web chat route",
                "description": "Pastikan route memakai core flow",
                "due_date": None,
                "priority": "medium",
            },
            "user_confirmation_text": "Buat task Review web chat route?",
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


def make_handler(
    *, actions_by_message: dict[str, ParsedAction] | None = None
) -> tuple[WebChatHttpHandler, FakeProgressOS]:
    progressos = FakeProgressOS()
    handler = WebChatHttpHandler(
        identity_service=CaptureIdentityService(
            authorizer=FakeAuthorizer(),
            progressos_user_resolver=FakeResolver(),
        ),
        capture_flow=CaptureFlow(
            parser=FakeParser(actions_by_message=actions_by_message or {}),
            progressos=progressos,
            pending=InMemoryPendingActionStore(ttl_seconds=60),
            correlation_id_factory=lambda: "corr-web-route",
        ),
        read_flow=ReadCommandFlow(
            progressos=FakeReadClient(),
            correlation_id_factory=lambda: "corr-web-route-read",
        ),
    )
    return handler, progressos


def test_web_chat_routed_request_rejects_message_type_without_message_payload() -> None:
    with pytest.raises(ValidationError, match="message is required"):
        WebChatRoutedRequest.model_validate({"type": "message"})


def test_web_chat_routed_request_rejects_confirmation_type_without_payload() -> None:
    with pytest.raises(ValidationError, match="confirmation is required"):
        WebChatRoutedRequest.model_validate({"type": "confirmation"})


@pytest.mark.asyncio
async def test_web_chat_http_handler_routes_dashboard_message() -> None:
    handler, _ = make_handler()

    response = await handler.handle(
        {
            "type": "message",
            "message": {
                "message_id": "msg-1",
                "session": {"session_id": "session-1", "user_id": "web-user-1"},
                "text": "/dashboard",
            },
        }
    )

    assert response["correlation_id"] == "corr-web-route-read"
    assert response["deliveries"] == [
        {
            "delivery_type": "text",
            "session_id": "session-1",
            "text": "Dashboard siap",
            "request_id": None,
        }
    ]


@pytest.mark.asyncio
async def test_web_chat_http_handler_routes_capture_message_and_confirmation() -> None:
    handler, progressos = make_handler(
        actions_by_message={"buat task review web chat route": make_task_action()}
    )

    draft_response = await handler.handle(
        {
            "type": "message",
            "message": {
                "message_id": "msg-1",
                "session": {"session_id": "session-1", "user_id": "web-user-1"},
                "text": "buat task review web chat route",
            },
        }
    )
    confirm_response = await handler.handle(
        {
            "type": "confirmation",
            "confirmation": {
                "request_id": "corr-web-route",
                "session": {"session_id": "session-1", "user_id": "web-user-1"},
                "decision": "confirm",
            },
        }
    )

    assert draft_response["correlation_id"] == "corr-web-route"
    assert draft_response["deliveries"][0]["delivery_type"] == "confirmation_request"
    assert confirm_response["correlation_id"] == "corr-web-route"
    assert confirm_response["deliveries"][0]["text"] == "Capture tersimpan."
    assert len(progressos.submitted_requests) == 1


@pytest.mark.asyncio
async def test_web_chat_http_handler_rejects_unknown_fields() -> None:
    handler, _ = make_handler()

    with pytest.raises(ValidationError):
        await handler.handle(
            {
                "type": "message",
                "message": {
                    "message_id": "msg-1",
                    "session": {"session_id": "session-1", "user_id": "web-user-1"},
                    "text": "/dashboard",
                },
                "unexpected": "value",
            }
        )
