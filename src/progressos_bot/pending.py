from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from progressos_bot.schemas import ParsedAction


@dataclass(frozen=True)
class PendingAction:
    original_text: str
    parsed_action: ParsedAction
    expires_at: datetime


class InMemoryPendingActionStore:
    def __init__(
        self,
        *,
        ttl_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ttl = timedelta(seconds=max(1, ttl_seconds))
        self._clock = clock or self._utc_now
        self._pending: dict[str, PendingAction] = {}

    def put(self, user_key: str, original_text: str, parsed_action: ParsedAction) -> None:
        self._pending[user_key] = PendingAction(
            original_text=original_text,
            parsed_action=parsed_action,
            expires_at=self._now() + self._ttl,
        )

    def discard(self, user_key: str) -> None:
        self._pending.pop(user_key, None)

    def pop(self, user_key: str) -> PendingAction | None:
        pending = self._pending.pop(user_key, None)
        if pending is None:
            return None
        if pending.expires_at <= self._now():
            return None
        return pending

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)
