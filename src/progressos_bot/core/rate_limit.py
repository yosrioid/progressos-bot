from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0

    def to_user_message(self) -> str:
        if self.allowed:
            return ""
        return f"Terlalu banyak request. Coba lagi dalam {self.retry_after_seconds} detik."


class RateLimiter(Protocol):
    def check(self, key: str) -> RateLimitResult: ...


class NoopRateLimiter:
    def check(self, key: str) -> RateLimitResult:
        del key
        return RateLimitResult(allowed=True)


class InMemoryRateLimiter:
    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._max_requests = max(1, max_requests)
        self._window = timedelta(seconds=max(1, window_seconds))
        self._clock = clock or self._utc_now
        self._requests: dict[str, deque[datetime]] = {}

    def check(self, key: str) -> RateLimitResult:
        now = self._now()
        requests = self._requests.setdefault(key, deque())
        cutoff = now - self._window
        while requests and requests[0] <= cutoff:
            requests.popleft()

        if len(requests) >= self._max_requests:
            retry_after = max(1, int((requests[0] + self._window - now).total_seconds()))
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

        requests.append(now)
        return RateLimitResult(allowed=True)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)
