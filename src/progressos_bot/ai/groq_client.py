import json
from collections.abc import Mapping
from typing import Any

from groq import AsyncGroq
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from progressos_bot.ai.prompts import SYSTEM_PROMPT, build_user_prompt


class GroqParserClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncGroq(api_key=api_key)
        self._model = model

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
        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(message=message, today=today)},
            ],
        )
        return response.choices[0].message.content
