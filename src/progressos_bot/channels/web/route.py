from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from progressos_bot.channels.web.adapter import WebChatChannelAdapter, WebChatInboundMessage
from progressos_bot.channels.web.gateway import (
    WebChatConfirmationPayload,
    WebChatGateway,
)
from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.core.identity import CaptureIdentityService
from progressos_bot.core.read_commands import ReadCommandFlow

WebChatRequestType = Literal["message", "confirmation"]


class WebChatRoutedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: WebChatRequestType
    message: WebChatInboundMessage | None = None
    confirmation: WebChatConfirmationPayload | None = None

    @model_validator(mode="after")
    def _check_payload_matches_type(self) -> "WebChatRoutedRequest":
        if self.type == "message" and self.message is None:
            raise ValueError("message is required when type is 'message'.")
        if self.type == "confirmation" and self.confirmation is None:
            raise ValueError("confirmation is required when type is 'confirmation'.")
        return self


class WebChatHttpHandler:
    def __init__(
        self,
        *,
        identity_service: CaptureIdentityService,
        capture_flow: CaptureFlow,
        read_flow: ReadCommandFlow,
    ) -> None:
        self._identity_service = identity_service
        self._capture_flow = capture_flow
        self._read_flow = read_flow

    async def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = WebChatRoutedRequest.model_validate(payload)
        gateway = WebChatGateway(
            adapter=WebChatChannelAdapter(),
            identity_service=self._identity_service,
            capture_flow=self._capture_flow,
            read_flow=self._read_flow,
        )
        if request.type == "message":
            assert request.message is not None
            response = await gateway.handle_message(request.message)
        else:
            assert request.confirmation is not None
            response = await gateway.handle_confirmation(request.confirmation)
        return response.model_dump(mode="json")
