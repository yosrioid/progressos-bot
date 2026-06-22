import pytest

from progressos_bot.identity import (
    ChannelUserIdentity,
    TelegramAllowlist,
    TelegramProgressOSUserMap,
    UserAuthorizationError,
    UserMappingError,
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


def test_telegram_allowlist_rejects_revoked_user() -> None:
    allowlist = TelegramAllowlist.from_csv("123,456", revoked_value="123")
    identity = ChannelUserIdentity(channel="telegram", channel_user_id="123")

    assert allowlist.is_revoked(identity)
    assert not allowlist.is_authorized(identity)
    with pytest.raises(UserAuthorizationError, match="dicabut"):
        allowlist.require_authorized(identity)


def test_telegram_progressos_user_map_resolves_configured_user() -> None:
    user_map = TelegramProgressOSUserMap.from_csv("123:77,456:88")
    identity = ChannelUserIdentity(channel="telegram", channel_user_id="123")

    assert user_map.resolve(identity) == "77"


def test_telegram_progressos_user_map_rejects_unmapped_user() -> None:
    user_map = TelegramProgressOSUserMap.from_csv("123:77")
    identity = ChannelUserIdentity(channel="telegram", channel_user_id="999")

    with pytest.raises(UserMappingError, match="belum terhubung"):
        user_map.resolve(identity)


def test_telegram_progressos_user_map_rejects_invalid_entries() -> None:
    with pytest.raises(ValueError, match="Invalid"):
        TelegramProgressOSUserMap.from_csv("123")
