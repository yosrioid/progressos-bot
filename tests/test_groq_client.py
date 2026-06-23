from types import SimpleNamespace
from typing import Any

import pytest

from progressos_bot.ai.groq_client import GroqParserClient


class FakeCompletions:
    def __init__(self, content: str | None) -> None:
        self.content = content
        self.requests: list[dict[str, Any]] = []

    async def create(self, **_kwargs: Any) -> SimpleNamespace:
        self.requests.append(_kwargs)
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


def make_structured_client(
    content: str | None,
    *,
    mode: str,
) -> GroqParserClient:
    client = GroqParserClient(
        api_key="fake-key",
        model="test-model",
        structured_output_mode=mode,
    )
    client._client = FakeGroqSdk(content=content)
    return client


def last_request(client: GroqParserClient) -> dict[str, Any]:
    return client._client.chat.completions.requests[-1]


@pytest.mark.asyncio
async def test_groq_parser_accepts_json_object_response() -> None:
    client = make_client('{"intent": "unsupported", "confidence": 0.9}')

    parsed = await client.parse_message(message="hapus semua task", today="2026-06-23")

    assert parsed == {"intent": "unsupported", "confidence": 0.9}
    assert "response_format" not in last_request(client)


@pytest.mark.asyncio
async def test_groq_parser_can_request_best_effort_structured_output() -> None:
    client = make_structured_client(
        '{"intent": "unsupported", "confidence": 0.9}',
        mode="best_effort",
    )

    await client.parse_message(message="hapus semua task", today="2026-06-23")

    response_format = last_request(client)["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "progressos_parser_response"
    assert response_format["json_schema"]["strict"] is False


@pytest.mark.asyncio
async def test_groq_parser_can_request_strict_structured_output() -> None:
    client = make_structured_client(
        '{"intent": "unsupported", "confidence": 0.9}',
        mode="strict",
    )

    await client.parse_message(message="hapus semua task", today="2026-06-23")

    response_format = last_request(client)["response_format"]
    schema = response_format["json_schema"]["schema"]
    assert response_format["json_schema"]["strict"] is True
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "intent",
        "confidence",
        "language",
        "payload",
        "user_confirmation_text",
    }


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
