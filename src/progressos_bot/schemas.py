from datetime import date as Date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Intent = Literal["create_task", "create_blocker", "log_work", "unsupported"]
Priority = Literal["low", "medium", "high", "urgent"]
Language = Literal["id", "en", "unknown"]
QuickCaptureType = Literal["task", "blocker", "work_log", "daily_progress", "learning"]


class CreateTaskPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    due_date: Date | None = None
    priority: Priority = "medium"


class CreateBlockerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    severity: Priority = "medium"


class LogWorkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    date: Date | None = None
    duration_minutes: int = Field(gt=0, le=10000)
    project_name: str | None = Field(default=None, min_length=1, max_length=120)


class UnsupportedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=300)


class ParsedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    confidence: float = Field(ge=0, le=1)
    language: Language
    payload: CreateTaskPayload | CreateBlockerPayload | LogWorkPayload | UnsupportedPayload
    user_confirmation_text: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def validate_payload_matches_intent(self) -> "ParsedAction":
        if self.intent == "create_task" and not isinstance(self.payload, CreateTaskPayload):
            raise ValueError("create_task intent requires CreateTaskPayload")
        if self.intent == "create_blocker" and not isinstance(
            self.payload, CreateBlockerPayload
        ):
            raise ValueError("create_blocker intent requires CreateBlockerPayload")
        if self.intent == "log_work" and not isinstance(self.payload, LogWorkPayload):
            raise ValueError("log_work intent requires LogWorkPayload")
        if self.intent == "unsupported" and not isinstance(self.payload, UnsupportedPayload):
            raise ValueError("unsupported intent requires UnsupportedPayload")
        return self


class ProgressOSActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["telegram"] = "telegram"
    source_user_id: str = Field(min_length=1)
    source_chat_id: str = Field(min_length=1)
    original_text: str = Field(min_length=1, max_length=5000)
    parsed_action: ParsedAction


class ProgressOSQuickCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: QuickCaptureType
    title: str = Field(min_length=1, max_length=180)
    project_name: str | None = Field(default=None, min_length=1, max_length=180)
    notes: str | None = Field(default=None, max_length=5000)
    date: Date | None = None
    duration_minutes: int | None = Field(default=None, gt=0)


class ProgressOSActionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str | None = None
    message: str | None = None
    action_id: str | None = None
    data: dict[str, Any] | None = None
    record: dict[str, Any] | None = None
    record_path: str | None = None

    def to_user_message(self) -> str:
        parts: list[str] = []
        if self.message:
            parts.append(self.message)
        if self.record_path:
            parts.append(f"Lokasi: {self.record_path}")
        if parts:
            return "\n".join(parts)
        return "Capture tersimpan."


class ProgressOSValidationErrorResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str
    errors: dict[str, list[str]] = Field(default_factory=dict)
