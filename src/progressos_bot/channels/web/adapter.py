from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from progressos_bot.channels.base import (
    ChannelMessage,
    ChannelUser,
    ConfirmationRequest,
)

WEB_CHAT_CHANNEL = "web_chat"


class WebChatSession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str = Field(min_length=1, max_length=255)
    user_id: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)


class WebChatInboundMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: str = Field(min_length=1, max_length=255)
    session: WebChatSession
    text: str = Field(min_length=1, max_length=5000)


WebChatDeliveryType = Literal["text", "confirmation_request"]


class WebChatDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    delivery_type: WebChatDeliveryType
    session_id: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=1000)
    request_id: str | None = Field(default=None, min_length=1, max_length=255)


@dataclass
class WebChatChannelAdapter:
    deliveries: list[WebChatDelivery] = field(default_factory=list)

    def build_message(self, inbound: WebChatInboundMessage) -> ChannelMessage:
        return ChannelMessage(
            channel=WEB_CHAT_CHANNEL,
            message_id=inbound.message_id,
            conversation_id=inbound.session.session_id,
            user=ChannelUser(
                channel=WEB_CHAT_CHANNEL,
                channel_user_id=inbound.session.user_id,
                display_name=inbound.session.display_name,
            ),
            text=inbound.text,
        )

    async def send_text(self, *, conversation_id: str, text: str) -> None:
        self.deliveries.append(
            WebChatDelivery(
                delivery_type="text",
                session_id=conversation_id,
                text=text,
            )
        )

    async def request_confirmation(self, request: ConfirmationRequest) -> None:
        self.deliveries.append(
            WebChatDelivery(
                delivery_type="confirmation_request",
                session_id=request.conversation_id,
                text=request.prompt_text,
                request_id=request.request_id,
            )
        )
