import pytest
from pydantic import ValidationError

from progressos_bot.schemas import ParsedAction


def test_create_task_payload_is_valid() -> None:
    action = ParsedAction.model_validate(
        {
            "intent": "create_task",
            "confidence": 0.91,
            "language": "id",
            "payload": {
                "title": "Follow up invoice client A",
                "description": None,
                "due_date": "2026-06-21",
                "priority": "high",
            },
            "user_confirmation_text": "Buat task Follow up invoice client A?",
        }
    )

    assert action.intent == "create_task"
    assert action.payload.title == "Follow up invoice client A"


def test_unknown_payload_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ParsedAction.model_validate(
            {
                "intent": "create_task",
                "confidence": 0.91,
                "language": "id",
                "payload": {
                    "title": "Follow up invoice client A",
                    "description": None,
                    "due_date": "2026-06-21",
                    "priority": "high",
                    "unexpected": "must fail",
                },
                "user_confirmation_text": "Buat task Follow up invoice client A?",
            }
        )


def test_intent_must_match_payload_shape() -> None:
    with pytest.raises(ValidationError):
        ParsedAction.model_validate(
            {
                "intent": "unsupported",
                "confidence": 0.91,
                "language": "id",
                "payload": {
                    "title": "Follow up invoice client A",
                    "description": None,
                    "due_date": None,
                    "priority": "high",
                },
                "user_confirmation_text": "Intent tidak didukung.",
            }
        )

