from dataclasses import dataclass
from typing import Literal

from progressos_bot.core.guided_capture import (
    GuidedCaptureDraft,
    GuidedCaptureField,
    GuidedCaptureIntent,
    guided_capture_fields,
)
from progressos_bot.schemas import Language

CliGuidedFormMode = Literal["create", "edit"]


@dataclass(frozen=True)
class CliGuidedCaptureForm:
    intent: GuidedCaptureIntent
    fields: tuple[GuidedCaptureField, ...]
    mode: CliGuidedFormMode = "create"

    @classmethod
    def for_intent(
        cls,
        intent: GuidedCaptureIntent,
        *,
        mode: CliGuidedFormMode = "create",
    ) -> "CliGuidedCaptureForm":
        return cls(intent=intent, fields=guided_capture_fields(intent), mode=mode)

    def prompt_lines(self) -> list[str]:
        lines = [f"Guided capture: {self.intent} ({self.mode})"]
        for field in self.fields:
            required = " required" if field.required else " optional"
            options = f" options={','.join(field.options)}" if field.options else ""
            lines.append(f"- {field.key}: {field.label} [{field.field_type}{required}{options}]")
        return lines

    def build_draft(
        self,
        values: dict[str, object],
        *,
        language: Language = "id",
        user_confirmation_text: str | None = None,
    ) -> GuidedCaptureDraft:
        return GuidedCaptureDraft.model_validate(
            {
                "intent": self.intent,
                "language": language,
                "payload": values,
                "user_confirmation_text": user_confirmation_text
                or _default_confirmation_text(self.intent, values),
                "original_text": f"guided:{self.intent}:{self.mode}",
            }
        )


def _default_confirmation_text(
    intent: GuidedCaptureIntent,
    values: dict[str, object],
) -> str:
    title = values.get("title")
    if not isinstance(title, str) or not title.strip():
        return f"Konfirmasi guided capture {intent}?"
    return f"Konfirmasi {intent} {title}?"
