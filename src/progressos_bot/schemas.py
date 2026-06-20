from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Intent = Literal["create_task", "unsupported"]
Priority = Literal["low", "medium", "high", "urgent"]
Language = Literal["id", "en", "unknown"]


class CreateTaskPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    priority: Priority = "medium"


class UnsupportedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=300)


class ParsedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    confidence: float = Field(ge=0, le=1)
    language: Language
    payload: CreateTaskPayload | UnsupportedPayload
    user_confirmation_text: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def validate_payload_matches_intent(self) -> "ParsedAction":
        if self.intent == "create_task" and not isinstance(self.payload, CreateTaskPayload):
            raise ValueError("create_task intent requires CreateTaskPayload")
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


class ProgressOSActionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    message: str | None = None
    action_id: str | None = None

