import pytest

from progressos_bot.bot import ProgressOSTelegramBot
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


def make_bot(
    *,
    allowed: str = "123",
    revoked: str = "",
    mappings: str = "123:77",
) -> ProgressOSTelegramBot:
    return ProgressOSTelegramBot(
        token="token",
        parser=object(),
        progressos=object(),
        authorizer=TelegramAllowlist.from_csv(allowed, revoked_value=revoked),
        user_map=TelegramProgressOSUserMap.from_csv(mappings),
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
