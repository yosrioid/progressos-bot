import json
from collections.abc import Mapping
from typing import Any, Literal, cast

from groq import AsyncGroq
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from progressos_bot.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from progressos_bot.ai.structured_schema import parser_response_format

StructuredOutputMode = Literal["off", "best_effort", "strict"]


class GroqParserClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        structured_output_mode: StructuredOutputMode = "off",
    ) -> None:
        self._client = AsyncGroq(api_key=api_key)
        self._model = model
        self._structured_output_mode = structured_output_mode

    async def parse_message(self, message: str, today: str) -> Mapping[str, Any]:
        content = await self._request_completion(message=message, today=today)
        if not content:
            raise ValueError("Groq returned an empty response")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Groq response must be a JSON object")
        return parsed

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _request_completion(self, message: str, today: str) -> str | None:
        request: dict[str, Any] = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(message=message, today=today)},
            ],
        }
        response_format = self._response_format()
        if response_format is not None:
            request["response_format"] = response_format

        response = await self._client.chat.completions.create(**request)
        return cast(str | None, response.choices[0].message.content)

    def _response_format(self) -> dict[str, Any] | None:
        if self._structured_output_mode == "off":
            return None
        return parser_response_format(strict=self._structured_output_mode == "strict")
