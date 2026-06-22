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


def test_create_blocker_payload_is_valid() -> None:
    action = ParsedAction.model_validate(
        {
            "intent": "create_blocker",
            "confidence": 0.89,
            "language": "id",
            "payload": {
                "title": "Blocked by missing API token",
                "description": "Need ProgressOS token from admin",
                "severity": "high",
            },
            "user_confirmation_text": "Catat blocker missing API token?",
        }
    )

    assert action.intent == "create_blocker"
    assert action.payload.title == "Blocked by missing API token"


def test_log_work_payload_is_valid() -> None:
    action = ParsedAction.model_validate(
        {
            "intent": "log_work",
            "confidence": 0.9,
            "language": "id",
            "payload": {
                "title": "Implement Telegram webhook",
                "description": "Finished webhook server draft",
                "date": "2026-06-22",
                "duration_minutes": 90,
                "project_name": "ProgressOS",
            },
            "user_confirmation_text": "Catat work log Implement Telegram webhook selama 90 menit?",
        }
    )

    assert action.intent == "log_work"
    assert action.payload.title == "Implement Telegram webhook"


def test_log_daily_progress_payload_is_valid() -> None:
    action = ParsedAction.model_validate(
        {
            "intent": "log_daily_progress",
            "confidence": 0.9,
            "language": "id",
            "payload": {
                "title": "Backend integration progress",
                "description": "Quick-capture client and Telegram confirmation are done",
                "date": "2026-06-22",
                "project_name": "ProgressOS",
            },
            "user_confirmation_text": "Catat daily progress Backend integration progress?",
        }
    )

    assert action.intent == "log_daily_progress"
    assert action.payload.title == "Backend integration progress"


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


def test_create_blocker_intent_rejects_task_payload_shape() -> None:
    with pytest.raises(ValidationError):
        ParsedAction.model_validate(
            {
                "intent": "create_blocker",
                "confidence": 0.91,
                "language": "id",
                "payload": {
                    "title": "Follow up invoice client A",
                    "description": None,
                    "due_date": None,
                    "priority": "high",
                },
                "user_confirmation_text": "Catat blocker?",
            }
        )


def test_log_work_intent_rejects_task_payload_shape() -> None:
    with pytest.raises(ValidationError):
        ParsedAction.model_validate(
            {
                "intent": "log_work",
                "confidence": 0.91,
                "language": "id",
                "payload": {
                    "title": "Follow up invoice client A",
                    "description": None,
                    "due_date": None,
                    "priority": "high",
                },
                "user_confirmation_text": "Catat work log?",
            }
        )


def test_log_daily_progress_intent_rejects_work_log_payload_shape() -> None:
    with pytest.raises(ValidationError):
        ParsedAction.model_validate(
            {
                "intent": "log_daily_progress",
                "confidence": 0.91,
                "language": "id",
                "payload": {
                    "title": "Implement Telegram webhook",
                    "description": None,
                    "date": "2026-06-22",
                    "duration_minutes": 90,
                    "project_name": "ProgressOS",
                },
                "user_confirmation_text": "Catat daily progress?",
            }
        )
