from datetime import date

from pydantic import ValidationError

from progressos_bot.ai.groq_client import GroqParserClient
from progressos_bot.schemas import ParsedAction


class MessageParser:
    def __init__(self, groq: GroqParserClient, min_confidence: float) -> None:
        self._groq = groq
        self._min_confidence = min_confidence

    async def parse(self, message: str, today: date | None = None) -> ParsedAction:
        current_date = today or date.today()
        raw = await self._groq.parse_message(message=message, today=current_date.isoformat())

        try:
            action = ParsedAction.model_validate(raw)
        except ValidationError:
            raise

        if action.confidence < self._min_confidence:
            raise ValueError(
                f"AI confidence {action.confidence:.2f} is below minimum {self._min_confidence:.2f}"
            )

        return action

