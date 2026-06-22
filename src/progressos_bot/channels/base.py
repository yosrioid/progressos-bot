from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

ConfirmationDecisionValue = Literal["confirm", "cancel"]
ChannelName = str
CHANNEL_NAME_PATTERN = r"^[a-z][a-z0-9_-]{0,49}$"


class ChannelUser(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: ChannelName = Field(pattern=CHANNEL_NAME_PATTERN)
    channel_user_id: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)


class ChannelMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: ChannelName = Field(pattern=CHANNEL_NAME_PATTERN)
    message_id: str = Field(min_length=1, max_length=255)
    conversation_id: str = Field(min_length=1, max_length=255)
    user: ChannelUser
    text: str = Field(min_length=1, max_length=5000)


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=255)
    conversation_id: str = Field(min_length=1, max_length=255)
    user: ChannelUser
    prompt_text: str = Field(min_length=1, max_length=1000)


class ConfirmationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=255)
    user: ChannelUser
    decision: ConfirmationDecisionValue


class ChannelAdapter(Protocol):
    async def send_text(self, *, conversation_id: str, text: str) -> None:
        """Send plain text to a channel conversation."""

    async def request_confirmation(self, request: ConfirmationRequest) -> None:
        """Ask the channel user to confirm or cancel a pending request."""
