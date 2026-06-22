from collections.abc import Mapping
from typing import Any

import pytest

from progressos_bot.ai.parser import MessageParser


class FakeGroqClient:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self.response = response

    async def parse_message(self, message: str, today: str) -> Mapping[str, Any]:
        assert message
        assert today
        return self.response


@pytest.mark.asyncio
async def test_parser_rejects_low_confidence() -> None:
    parser = MessageParser(
        groq=FakeGroqClient(
            {
                "intent": "create_task",
                "confidence": 0.2,
                "language": "id",
                "payload": {
                    "title": "Follow up invoice client A",
                    "description": None,
                    "due_date": None,
                    "priority": "medium",
                },
                "user_confirmation_text": "Buat task Follow up invoice client A?",
            }
        ),
        min_confidence=0.75,
    )

    with pytest.raises(ValueError, match="below minimum"):
        await parser.parse("buat task follow up invoice")


@pytest.mark.asyncio
async def test_parser_accepts_supported_action() -> None:
    parser = MessageParser(
        groq=FakeGroqClient(
            {
                "intent": "create_task",
                "confidence": 0.91,
                "language": "id",
                "payload": {
                    "title": "Follow up invoice client A",
                    "description": None,
                    "due_date": None,
                    "priority": "medium",
                },
                "user_confirmation_text": "Buat task Follow up invoice client A?",
            }
        ),
        min_confidence=0.75,
    )

    action = await parser.parse("buat task follow up invoice")

    assert action.intent == "create_task"


@pytest.mark.asyncio
async def test_parser_accepts_blocker_action() -> None:
    parser = MessageParser(
        groq=FakeGroqClient(
            {
                "intent": "create_blocker",
                "confidence": 0.88,
                "language": "id",
                "payload": {
                    "title": "Blocked by missing API token",
                    "description": "Need ProgressOS token from admin",
                    "severity": "high",
                },
                "user_confirmation_text": "Catat blocker missing API token?",
            }
        ),
        min_confidence=0.75,
    )

    action = await parser.parse("catat blocker token API belum ada")

    assert action.intent == "create_blocker"


@pytest.mark.asyncio
async def test_parser_accepts_work_log_action() -> None:
    parser = MessageParser(
        groq=FakeGroqClient(
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
                "user_confirmation_text": "Catat work log Implement Telegram webhook?",
            }
        ),
        min_confidence=0.75,
    )

    action = await parser.parse("catat kerja 90 menit implement webhook Telegram")

    assert action.intent == "log_work"


@pytest.mark.asyncio
async def test_parser_accepts_daily_progress_action() -> None:
    parser = MessageParser(
        groq=FakeGroqClient(
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
        ),
        min_confidence=0.75,
    )

    action = await parser.parse("catat daily progress integrasi backend selesai")

    assert action.intent == "log_daily_progress"


@pytest.mark.asyncio
async def test_parser_accepts_learning_action() -> None:
    parser = MessageParser(
        groq=FakeGroqClient(
            {
                "intent": "capture_learning",
                "confidence": 0.9,
                "language": "id",
                "payload": {
                    "title": "Telegram webhook retry strategy",
                    "description": "Use idempotency key when retrying quick-capture writes",
                    "date": "2026-06-22",
                    "project_name": "ProgressOS",
                },
                "user_confirmation_text": "Catat learning Telegram webhook retry strategy?",
            }
        ),
        min_confidence=0.75,
    )

    action = await parser.parse("catat learning retry webhook pakai idempotency key")

    assert action.intent == "capture_learning"
