from dataclasses import dataclass, field

from progressos_bot.channels.base import (
    ChannelMessage,
    ChannelUser,
    ConfirmationRequest,
)


@dataclass(frozen=True)
class CliDelivery:
    conversation_id: str
    text: str


@dataclass
class CliChannelAdapter:
    sent_texts: list[CliDelivery] = field(default_factory=list)
    confirmation_requests: list[ConfirmationRequest] = field(default_factory=list)

    def build_message(
        self,
        *,
        text: str,
        user_id: str = "local-admin",
        conversation_id: str = "local-cli",
        message_id: str = "stdin",
    ) -> ChannelMessage:
        user = ChannelUser(
            channel="cli",
            channel_user_id=user_id,
            display_name=user_id,
        )
        return ChannelMessage(
            channel="cli",
            message_id=message_id,
            conversation_id=conversation_id,
            user=user,
            text=text,
        )

    async def send_text(self, *, conversation_id: str, text: str) -> None:
        self.sent_texts.append(CliDelivery(conversation_id=conversation_id, text=text))

    async def request_confirmation(self, request: ConfirmationRequest) -> None:
        self.confirmation_requests.append(request)
