from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from progressos_bot.ai.groq_client import GroqParserClient
from progressos_bot.schemas import ParsedAction


class MessageParser:
    def __init__(
        self,
        groq: GroqParserClient,
        min_confidence: float,
        *,
        timezone_name: str = "Asia/Jakarta",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._groq = groq
        self._min_confidence = min_confidence
        self._timezone = ZoneInfo(timezone_name)
        self._clock = clock or self._now

    async def parse(self, message: str, today: date | None = None) -> ParsedAction:
        current_date = today or self._today()
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

    def _today(self) -> date:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=self._timezone)
        return value.astimezone(self._timezone).date()

    def _now(self) -> datetime:
        return datetime.now(self._timezone)
