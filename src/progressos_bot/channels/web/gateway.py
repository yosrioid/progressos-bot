from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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

WebChatConfirmationDecision = Literal["confirm", "cancel"]


class WebChatConfirmationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=255)
    session: WebChatSession
    decision: WebChatConfirmationDecision


class WebChatGatewayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: str | None = Field(default=None, min_length=1, max_length=255)
    deliveries: list[WebChatDelivery]


class WebChatGateway:
    def __init__(
        self,
        *,
        adapter: WebChatChannelAdapter,
        identity_service: CaptureIdentityService,
        capture_flow: CaptureFlow,
        read_flow: ReadCommandFlow,
    ) -> None:
        self._adapter = adapter
        self._identity_service = identity_service
        self._capture_flow = capture_flow
        self._read_flow = read_flow

    async def handle_message(
        self,
        inbound: WebChatInboundMessage,
    ) -> WebChatGatewayResponse:
        message = self._adapter.build_message(inbound)
        self._identity_service.resolve_for_capture(
            ChannelUserIdentity(
                channel=message.user.channel,
                channel_user_id=message.user.channel_user_id,
            )
        )

        if message.text.strip() == "/dashboard":
            read_result = await self._read_flow.dashboard()
            await self._adapter.send_text(
                conversation_id=message.conversation_id,
                text=read_result.user_message,
            )
            return WebChatGatewayResponse(
                correlation_id=read_result.correlation_id,
                deliveries=self._adapter.drain_deliveries(),
            )

        capture_result = await self._capture_flow.begin_capture(
            user_key=_web_chat_user_key(inbound.session),
            original_text=message.text,
        )
        if capture_result.status == "confirmation_required":
            await self._adapter.request_confirmation(
                ConfirmationRequest(
                    request_id=capture_result.correlation_id,
                    conversation_id=message.conversation_id,
                    user=message.user,
                    prompt_text=capture_result.user_message,
                )
            )
        else:
            await self._adapter.send_text(
                conversation_id=message.conversation_id,
                text=capture_result.user_message,
            )

        return WebChatGatewayResponse(
            correlation_id=capture_result.correlation_id,
            deliveries=self._adapter.drain_deliveries(),
        )

    async def handle_confirmation(
        self,
        payload: WebChatConfirmationPayload,
    ) -> WebChatGatewayResponse:
        if payload.decision == "cancel":
            self._capture_flow.cancel_capture(user_key=_web_chat_user_key(payload.session))
            await self._adapter.send_text(
                conversation_id=payload.session.session_id,
                text="Capture dibatalkan.",
            )
            return WebChatGatewayResponse(deliveries=self._adapter.drain_deliveries())

        resolved = self._identity_service.resolve_for_capture(
            ChannelUserIdentity(
                channel=WEB_CHAT_CHANNEL,
                channel_user_id=payload.session.user_id,
            )
        )
        result = await self._capture_flow.submit_confirmed_capture(
            user_key=_web_chat_user_key(payload.session),
            source=WEB_CHAT_CHANNEL,
            source_user_id=payload.session.user_id,
            source_chat_id=payload.session.session_id,
            progressos_user_id=resolved.progressos_user_id,
        )
        await self._adapter.send_text(
            conversation_id=payload.session.session_id,
            text=result.user_message,
        )
        return WebChatGatewayResponse(
            correlation_id=result.correlation_id,
            deliveries=self._adapter.drain_deliveries(),
        )


def _web_chat_user_key(session: WebChatSession) -> str:
    return f"{WEB_CHAT_CHANNEL}:{session.user_id}"
