from types import SimpleNamespace
from typing import Any

import pytest

from progressos_bot.ai.groq_client import GroqParserClient


class FakeCompletions:
    def __init__(self, content: str | None) -> None:
        self.content = content

    async def create(self, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeChat:
    def __init__(self, content: str | None) -> None:
        self.completions = FakeCompletions(content=content)


class FakeGroqSdk:
    def __init__(self, content: str | None) -> None:
        self.chat = FakeChat(content=content)


def make_client(content: str | None) -> GroqParserClient:
    client = GroqParserClient(api_key="fake-key", model="test-model")
    client._client = FakeGroqSdk(content=content)
    return client


@pytest.mark.asyncio
async def test_groq_parser_accepts_json_object_response() -> None:
    client = make_client('{"intent": "unsupported", "confidence": 0.9}')

    parsed = await client.parse_message(message="hapus semua task", today="2026-06-23")

    assert parsed == {"intent": "unsupported", "confidence": 0.9}


@pytest.mark.asyncio
async def test_groq_parser_rejects_empty_response() -> None:
    client = make_client(None)

    with pytest.raises(ValueError, match="empty response"):
        await client.parse_message(message="buat task", today="2026-06-23")


@pytest.mark.asyncio
async def test_groq_parser_rejects_malformed_json() -> None:
    client = make_client("{not-json")

    with pytest.raises(ValueError):
        await client.parse_message(message="buat task", today="2026-06-23")


@pytest.mark.asyncio
async def test_groq_parser_rejects_non_object_json() -> None:
    client = make_client('[{"intent": "create_task"}]')

    with pytest.raises(ValueError, match="JSON object"):
        await client.parse_message(message="buat task", today="2026-06-23")
