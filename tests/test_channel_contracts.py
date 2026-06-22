from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from progressos_bot.channels.base import (
    ChannelAdapter,
    ChannelMessage,
    ChannelUser,
    ConfirmationDecision,
    ConfirmationRequest,
)


@dataclass
class FakeChannelAdapter:
    sent_texts: list[tuple[str, str]] = field(default_factory=list)
    confirmation_requests: list[ConfirmationRequest] = field(default_factory=list)

    async def send_text(self, *, conversation_id: str, text: str) -> None:
        self.sent_texts.append((conversation_id, text))

    async def request_confirmation(self, request: ConfirmationRequest) -> None:
        self.confirmation_requests.append(request)


def test_channel_message_accepts_non_telegram_channel() -> None:
    user = ChannelUser(
        channel="discord",
        channel_user_id="user-123",
        display_name="Ryo",
    )

    message = ChannelMessage(
        channel="discord",
        message_id="message-1",
        conversation_id="conversation-1",
        user=user,
        text="Buat task review PR",
    )

    assert message.user.channel == "discord"
    assert message.text == "Buat task review PR"


def test_channel_contracts_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ChannelUser.model_validate(
            {
                "channel": "telegram",
                "channel_user_id": "123",
                "unexpected": "value",
            }
        )


def test_channel_contracts_reject_invalid_channel_name() -> None:
    with pytest.raises(ValidationError):
        ChannelUser(channel="Telegram Bot", channel_user_id="123")


def test_confirmation_decision_allows_confirm_and_cancel_only() -> None:
    user = ChannelUser(channel="telegram", channel_user_id="123")

    confirm = ConfirmationDecision(
        request_id="request-1",
        user=user,
        decision="confirm",
    )
    cancel = ConfirmationDecision(
        request_id="request-1",
        user=user,
        decision="cancel",
    )

    assert confirm.decision == "confirm"
    assert cancel.decision == "cancel"
    with pytest.raises(ValidationError):
        ConfirmationDecision(
            request_id="request-1",
            user=user,
            decision="maybe",
        )


def test_channel_contracts_are_frozen() -> None:
    user = ChannelUser(channel="telegram", channel_user_id="123")

    with pytest.raises(ValidationError):
        user.channel_user_id = "456"


@pytest.mark.asyncio
async def test_channel_adapter_protocol_shape() -> None:
    adapter: ChannelAdapter = FakeChannelAdapter()
    request = ConfirmationRequest(
        request_id="request-1",
        conversation_id="chat-1",
        user=ChannelUser(channel="telegram", channel_user_id="123"),
        prompt_text="Confirm?",
    )

    await adapter.send_text(conversation_id="chat-1", text="Hello")
    await adapter.request_confirmation(request)

    assert isinstance(adapter, FakeChannelAdapter)
    assert adapter.sent_texts == [("chat-1", "Hello")]
    assert adapter.confirmation_requests == [request]
