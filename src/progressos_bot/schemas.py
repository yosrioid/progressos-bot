from datetime import date as Date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Intent = Literal[
    "create_task",
    "create_blocker",
    "log_work",
    "log_daily_progress",
    "capture_learning",
    "unsupported",
]
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


class LogDailyProgressPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    date: Date | None = None
    project_name: str | None = Field(default=None, min_length=1, max_length=120)


class CaptureLearningPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    date: Date | None = None
    project_name: str | None = Field(default=None, min_length=1, max_length=120)


class UnsupportedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=300)


class ParsedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    confidence: float = Field(ge=0, le=1)
    language: Language
    payload: (
        CreateTaskPayload
        | CreateBlockerPayload
        | LogWorkPayload
        | LogDailyProgressPayload
        | CaptureLearningPayload
        | UnsupportedPayload
    )
    user_confirmation_text: str = Field(min_length=5, max_length=500)

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
        if intent == "unsupported":
            return {**data, "payload": UnsupportedPayload.model_validate(payload)}

        return data

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
        if self.intent == "log_daily_progress" and not isinstance(
            self.payload, LogDailyProgressPayload
        ):
            raise ValueError("log_daily_progress intent requires LogDailyProgressPayload")
        if self.intent == "capture_learning" and not isinstance(
            self.payload, CaptureLearningPayload
        ):
            raise ValueError("capture_learning intent requires CaptureLearningPayload")
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


class ProgressOSStandupItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    name: str | None = None
    summary: str | None = None
    status: str | None = None
    project_name: str | None = None

    def to_user_line(self, index: int) -> str:
        label = self.title or self.name or self.summary or "Item standup"
        details = []
        if self.project_name:
            details.append(self.project_name)
        if self.status:
            details.append(self.status)
        suffix = f" ({', '.join(details)})" if details else ""
        return f"{index}. {label}{suffix}"


class ProgressOSStandupResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str | None = None
    items: list[ProgressOSStandupItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_items(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "items" in data:
            return data

        raw_data = data.get("data")
        if isinstance(raw_data, list):
            return {**data, "items": raw_data}

        standup = data.get("standup")
        if isinstance(standup, list):
            return {**data, "items": standup}

        return data

    def to_user_message(self) -> str:
        if not self.items:
            return self.message or "Tidak ada item standup."

        header = self.message or "Standup:"
        lines = [item.to_user_line(index) for index, item in enumerate(self.items[:10], start=1)]
        if len(self.items) > 10:
            lines.append(f"...dan {len(self.items) - 10} item lain.")
        return "\n".join([header, *lines])


class ProgressOSDashboardItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    name: str | None = None
    label: str | None = None
    value: str | int | float | None = None
    count: int | None = None

    def to_user_line(self, index: int) -> str:
        label = self.title or self.name or self.label or "Metric"
        value = self.value if self.value is not None else self.count
        if value is None:
            return f"{index}. {label}"
        return f"{index}. {label}: {value}"


class ProgressOSDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str | None = None
    items: list[ProgressOSDashboardItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_items(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "items" in data:
            return data

        raw_data = data.get("data")
        if isinstance(raw_data, list):
            return {**data, "items": raw_data}

        metrics = data.get("metrics")
        if isinstance(metrics, list):
            return {**data, "items": metrics}

        return data

    def to_user_message(self) -> str:
        if not self.items:
            return self.message or "Tidak ada ringkasan dashboard."

        header = self.message or "Dashboard:"
        lines = [item.to_user_line(index) for index, item in enumerate(self.items[:10], start=1)]
        if len(self.items) > 10:
            lines.append(f"...dan {len(self.items) - 10} metrik lain.")
        return "\n".join([header, *lines])


class ProgressOSSearchResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    name: str | None = None
    type: str | None = None
    excerpt: str | None = None
    record_path: str | None = None

    def to_user_line(self, index: int) -> str:
        label = self.title or self.name or "Hasil pencarian"
        prefix = f"[{self.type}] " if self.type else ""
        path = f" - {self.record_path}" if self.record_path else ""
        if self.excerpt:
            return f"{index}. {prefix}{label}: {self.excerpt}{path}"
        return f"{index}. {prefix}{label}{path}"


class ProgressOSSearchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str | None = None
    results: list[ProgressOSSearchResult] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_results(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "results" in data:
            return data

        raw_data = data.get("data")
        if isinstance(raw_data, list):
            return {**data, "results": raw_data}

        items = data.get("items")
        if isinstance(items, list):
            return {**data, "results": items}

        return data

    def to_user_message(self) -> str:
        if not self.results:
            return self.message or "Tidak ada hasil pencarian."

        header = self.message or "Hasil pencarian:"
        lines = [
            result.to_user_line(index) for index, result in enumerate(self.results[:10], start=1)
        ]
        if len(self.results) > 10:
            lines.append(f"...dan {len(self.results) - 10} hasil lain.")
        return "\n".join([header, *lines])
