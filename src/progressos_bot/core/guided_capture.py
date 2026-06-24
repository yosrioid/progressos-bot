from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from progressos_bot.channels.base import ChannelAdapter, ChannelMessage, ConfirmationRequest
from progressos_bot.core.capture_flow import CaptureDraftResult, CaptureFlow, CaptureSubmitResult
from progressos_bot.schemas import (
    CaptureLearningPayload,
    CreateBlockerPayload,
    CreateTaskPayload,
    Language,
    LogDailyProgressPayload,
    LogWorkPayload,
    ParsedAction,
    Priority,
)

GuidedCaptureIntent = Literal[
    "create_task",
    "create_blocker",
    "log_work",
    "log_daily_progress",
    "capture_learning",
]
GuidedCapturePayload = (
    CreateTaskPayload
    | CreateBlockerPayload
    | LogWorkPayload
    | LogDailyProgressPayload
    | CaptureLearningPayload
)
GuidedCaptureFieldType = Literal["text", "date", "duration_minutes", "priority"]


class GuidedCaptureField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    field_type: GuidedCaptureFieldType
    required: bool = True
    options: tuple[str, ...] = ()


class GuidedCaptureDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: GuidedCaptureIntent
    language: Language = "id"
    payload: GuidedCapturePayload
    user_confirmation_text: str = Field(min_length=5, max_length=500)
    original_text: str = Field(default="guided capture", min_length=1, max_length=5000)

    @model_validator(mode="before")
    @classmethod
    def coerce_payload_for_intent(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        intent = data.get("intent")
        payload = data.get("payload")
        if not isinstance(payload, dict):
            return data

        if intent == "create_task":
            return {**data, "payload": CreateTaskPayload.model_validate(payload)}
        if intent == "create_blocker":
            return {**data, "payload": CreateBlockerPayload.model_validate(payload)}
        if intent == "log_work":
            return {**data, "payload": LogWorkPayload.model_validate(payload)}
        if intent == "log_daily_progress":
            return {**data, "payload": LogDailyProgressPayload.model_validate(payload)}
        if intent == "capture_learning":
            return {**data, "payload": CaptureLearningPayload.model_validate(payload)}

        return data

    @model_validator(mode="after")
    def validate_as_parsed_action(self) -> "GuidedCaptureDraft":
        self.to_parsed_action()
        return self

    def to_parsed_action(self) -> ParsedAction:
        return ParsedAction.model_validate(
            {
                "intent": self.intent,
                "confidence": 1.0,
                "language": self.language,
                "payload": self.payload.model_dump(mode="json"),
                "user_confirmation_text": self.user_confirmation_text,
            }
        )

    def preview_lines(self) -> list[str]:
        payload = self.payload.model_dump(mode="json", exclude_none=True)
        lines = [
            f"Intent: {self.intent}",
            f"Title: {payload['title']}",
        ]
        for key, value in payload.items():
            if key == "title":
                continue
            lines.append(f"{_format_field_label(key)}: {value}")
        return lines

    def apply_payload_edit(
        self,
        changes: dict[str, object],
        *,
        user_confirmation_text: str | None = None,
    ) -> "GuidedCaptureDraft":
        payload = self.payload.model_dump(mode="json")
        payload.update(changes)
        return GuidedCaptureDraft.model_validate(
            {
                "intent": self.intent,
                "language": self.language,
                "payload": payload,
                "user_confirmation_text": user_confirmation_text
                or self.user_confirmation_text,
                "original_text": self.original_text,
            }
        )


def _format_field_label(value: str) -> str:
    return value.replace("_", " ").title()


class GuidedCaptureChannelFlow:
    def __init__(
        self,
        *,
        capture_flow: CaptureFlow,
        channel: ChannelAdapter,
    ) -> None:
        self._capture_flow = capture_flow
        self._channel = channel

    async def request_confirmation(
        self,
        *,
        message: ChannelMessage,
        draft: GuidedCaptureDraft,
    ) -> CaptureDraftResult:
        result = self._capture_flow.begin_parsed_capture(
            user_key=_channel_user_key(message),
            original_text=draft.original_text,
            action=draft.to_parsed_action(),
        )
        if result.status != "confirmation_required":
            await self._channel.send_text(
                conversation_id=message.conversation_id,
                text=result.user_message,
            )
            return result

        await self._channel.request_confirmation(
            ConfirmationRequest(
                request_id=result.correlation_id,
                conversation_id=message.conversation_id,
                user=message.user,
                prompt_text="\n".join([result.user_message, "", *draft.preview_lines()]),
            )
        )
        return result

    async def submit_confirmed(
        self,
        *,
        message: ChannelMessage,
        progressos_user_id: str | None,
    ) -> CaptureSubmitResult:
        return await self._capture_flow.submit_confirmed_capture(
            user_key=_channel_user_key(message),
            source=message.channel,
            source_user_id=message.user.channel_user_id,
            source_chat_id=message.conversation_id,
            progressos_user_id=progressos_user_id,
        )


def _channel_user_key(message: ChannelMessage) -> str:
    return f"{message.user.channel}:{message.user.channel_user_id}"


def guided_capture_fields(intent: GuidedCaptureIntent) -> tuple[GuidedCaptureField, ...]:
    return _GUIDED_CAPTURE_FIELDS[intent]


_PRIORITY_OPTIONS: tuple[Priority, ...] = ("low", "medium", "high", "urgent")
_GUIDED_CAPTURE_FIELDS: dict[GuidedCaptureIntent, tuple[GuidedCaptureField, ...]] = {
    "create_task": (
        GuidedCaptureField(key="title", label="Title", field_type="text"),
        GuidedCaptureField(
            key="description",
            label="Description",
            field_type="text",
            required=False,
        ),
        GuidedCaptureField(
            key="due_date",
            label="Due date",
            field_type="date",
            required=False,
        ),
        GuidedCaptureField(
            key="priority",
            label="Priority",
            field_type="priority",
            options=_PRIORITY_OPTIONS,
        ),
    ),
    "create_blocker": (
        GuidedCaptureField(key="title", label="Title", field_type="text"),
        GuidedCaptureField(
            key="description",
            label="Description",
            field_type="text",
            required=False,
        ),
        GuidedCaptureField(
            key="severity",
            label="Severity",
            field_type="priority",
            options=_PRIORITY_OPTIONS,
        ),
    ),
    "log_work": (
        GuidedCaptureField(key="title", label="Title", field_type="text"),
        GuidedCaptureField(
            key="description",
            label="Description",
            field_type="text",
            required=False,
        ),
        GuidedCaptureField(key="date", label="Date", field_type="date", required=False),
        GuidedCaptureField(
            key="duration_minutes",
            label="Duration",
            field_type="duration_minutes",
        ),
        GuidedCaptureField(
            key="project_name",
            label="Project",
            field_type="text",
            required=False,
        ),
    ),
    "log_daily_progress": (
        GuidedCaptureField(key="title", label="Title", field_type="text"),
        GuidedCaptureField(
            key="description",
            label="Description",
            field_type="text",
            required=False,
        ),
        GuidedCaptureField(key="date", label="Date", field_type="date", required=False),
        GuidedCaptureField(
            key="project_name",
            label="Project",
            field_type="text",
            required=False,
        ),
    ),
    "capture_learning": (
        GuidedCaptureField(key="title", label="Title", field_type="text"),
        GuidedCaptureField(
            key="description",
            label="Description",
            field_type="text",
            required=False,
        ),
        GuidedCaptureField(key="date", label="Date", field_type="date", required=False),
        GuidedCaptureField(
            key="project_name",
            label="Project",
            field_type="text",
            required=False,
        ),
    ),
}
