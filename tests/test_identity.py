import pytest

from progressos_bot.identity import (
    ChannelUserIdentity,
    TelegramAllowlist,
    UserAuthorizationError,
)


def test_telegram_allowlist_authorizes_configured_user() -> None:
    allowlist = TelegramAllowlist.from_csv("123, 456")
    identity = ChannelUserIdentity(channel="telegram", channel_user_id="123")

    assert allowlist.is_authorized(identity)


def test_telegram_allowlist_rejects_unknown_user() -> None:
    allowlist = TelegramAllowlist.from_csv("123")
    identity = ChannelUserIdentity(channel="telegram", channel_user_id="999")

    with pytest.raises(UserAuthorizationError, match="belum diizinkan"):
        allowlist.require_authorized(identity)


def test_empty_telegram_allowlist_rejects_all_users() -> None:
    allowlist = TelegramAllowlist.from_csv("")
    identity = ChannelUserIdentity(channel="telegram", channel_user_id="123")

    assert not allowlist.is_authorized(identity)
