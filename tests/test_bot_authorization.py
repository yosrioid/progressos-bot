import pytest

from progressos_bot.bot import ProgressOSTelegramBot
from progressos_bot.core.admin import AdminInfoService, ConfigurationDiagnostics, VersionInfo
from progressos_bot.core.rate_limit import RateLimitResult
from progressos_bot.identity import TelegramAllowlist, TelegramProgressOSUserMap


class FakeMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class FakeUpdate:
    def __init__(self, user_id: int) -> None:
        self.message = FakeMessage()
        self.effective_user = FakeUser(user_id)


class FakeRateLimiter:
    def __init__(self, result: RateLimitResult) -> None:
        self.result = result
        self.checked_keys: list[str] = []

    def check(self, key: str) -> RateLimitResult:
        self.checked_keys.append(key)
        return self.result


def make_bot(
    *,
    allowed: str = "123",
    revoked: str = "",
    mappings: str = "123:77",
    rate_limiter: FakeRateLimiter | None = None,
) -> ProgressOSTelegramBot:
    return ProgressOSTelegramBot(
        token="token",
        parser=object(),
        progressos=object(),
        authorizer=TelegramAllowlist.from_csv(allowed, revoked_value=revoked),
        user_map=TelegramProgressOSUserMap.from_csv(mappings),
        admin_info=AdminInfoService(
            version_info=VersionInfo(
                app_name="progressos-bot",
                app_version="0.1.0",
                app_env="local",
                run_mode="polling",
                log_format="text",
            ),
            diagnostics=ConfigurationDiagnostics(
                app_env="local",
                run_mode="polling",
                log_format="text",
                capture_enabled_intents={"create_task"},
                capture_pre_parser_guard_mode="off",
                pending_store_enabled=False,
                retry_queue_enabled=False,
                allowlist_configured=bool(allowed),
                user_map_configured=bool(mappings),
                webhook_secret_configured=False,
            ),
        ),
        rate_limiter=rate_limiter,
    )


@pytest.mark.asyncio
async def test_authorize_mapped_message_allows_mapped_user() -> None:
    bot = make_bot()
    update = FakeUpdate(123)

    assert await bot._authorize_mapped_message(update)
    assert update.message.replies == []


@pytest.mark.asyncio
async def test_authorize_mapped_message_rejects_unmapped_user() -> None:
    bot = make_bot(mappings="456:88")
    update = FakeUpdate(123)

    assert not await bot._authorize_mapped_message(update)
    assert update.message.replies == ["User belum terhubung ke ProgressOS."]


@pytest.mark.asyncio
async def test_authorize_mapped_message_rejects_revoked_user_before_mapping() -> None:
    bot = make_bot(revoked="123")
    update = FakeUpdate(123)

    assert not await bot._authorize_mapped_message(update)
    assert update.message.replies == ["Akses user ini sudah dicabut."]


@pytest.mark.asyncio
async def test_handle_message_rejects_rate_limited_user_before_parsing() -> None:
    limiter = FakeRateLimiter(RateLimitResult(allowed=False, retry_after_seconds=30))
    bot = make_bot(rate_limiter=limiter)
    update = FakeUpdate(123)

    await bot._handle_message(update, object())

    assert limiter.checked_keys == ["123"]
    assert update.message.replies == ["Terlalu banyak request. Coba lagi dalam 30 detik."]
