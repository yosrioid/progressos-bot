from datetime import UTC, datetime, timedelta

from progressos_bot.core.rate_limit import InMemoryRateLimiter, NoopRateLimiter


def test_noop_rate_limiter_always_allows() -> None:
    limiter = NoopRateLimiter()

    result = limiter.check("user-1")

    assert result.allowed is True
    assert result.to_user_message() == ""


def test_in_memory_rate_limiter_rejects_after_limit() -> None:
    now = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)

    def clock() -> datetime:
        return now

    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60, clock=clock)

    assert limiter.check("user-1").allowed is True
    assert limiter.check("user-1").allowed is True
    rejected = limiter.check("user-1")

    assert rejected.allowed is False
    assert rejected.retry_after_seconds == 60
    assert rejected.to_user_message() == "Terlalu banyak request. Coba lagi dalam 60 detik."


def test_in_memory_rate_limiter_allows_after_window() -> None:
    current_time = datetime(2026, 6, 22, 10, 0, tzinfo=UTC)

    def clock() -> datetime:
        return current_time

    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60, clock=clock)
    assert limiter.check("user-1").allowed is True
    assert limiter.check("user-1").allowed is False

    current_time = current_time + timedelta(seconds=61)

    assert limiter.check("user-1").allowed is True


def test_in_memory_rate_limiter_scopes_by_key() -> None:
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60)

    assert limiter.check("user-1").allowed is True
    assert limiter.check("user-1").allowed is False
    assert limiter.check("user-2").allowed is True
