from collections.abc import Iterable
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from progressos_bot.channels.base import CHANNEL_NAME_PATTERN


class ChannelUserIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str = Field(pattern=CHANNEL_NAME_PATTERN)
    channel_user_id: str = Field(min_length=1)


class UserAuthorizationError(RuntimeError):
    pass


class UserMappingError(RuntimeError):
    pass


class UserAuthorizer(Protocol):
    def require_authorized(self, identity: ChannelUserIdentity) -> None: ...


class ProgressOSUserResolver(Protocol):
    def resolve(self, identity: ChannelUserIdentity) -> str: ...


class ChannelAllowlist:
    _channel = "telegram"

    def __init__(
        self,
        allowed_user_ids: Iterable[str],
        revoked_user_ids: Iterable[str] | None = None,
    ) -> None:
        self._allowed_user_ids = {
            user_id.strip() for user_id in allowed_user_ids if user_id.strip()
        }
        self._revoked_user_ids = {
            user_id.strip()
            for user_id in (revoked_user_ids or [])
            if user_id.strip()
        }

    @classmethod
    def from_csv(cls, value: str, revoked_value: str = "") -> "ChannelAllowlist":
        return cls(value.split(","), revoked_value.split(","))

    def is_revoked(self, identity: ChannelUserIdentity) -> bool:
        return (
            identity.channel == self._channel
            and identity.channel_user_id in self._revoked_user_ids
        )

    def is_authorized(self, identity: ChannelUserIdentity) -> bool:
        return (
            identity.channel == self._channel
            and identity.channel_user_id in self._allowed_user_ids
            and not self.is_revoked(identity)
        )

    def require_authorized(self, identity: ChannelUserIdentity) -> None:
        if self.is_revoked(identity):
            raise UserAuthorizationError("Akses user ini sudah dicabut.")
        if not self.is_authorized(identity):
            raise UserAuthorizationError("User belum diizinkan memakai bot ini.")


class TelegramAllowlist(ChannelAllowlist):
    _channel = "telegram"


class WebChatAllowlist(ChannelAllowlist):
    _channel = "web_chat"


class ChannelProgressOSUserMap:
    _channel = "telegram"

    def __init__(self, mappings: dict[str, str]) -> None:
        self._mappings = mappings

    @classmethod
    def from_csv(cls, value: str) -> "ChannelProgressOSUserMap":
        mappings: dict[str, str] = {}
        for entry in value.split(","):
            stripped = entry.strip()
            if not stripped:
                continue
            channel_user_id, separator, progressos_user_id = stripped.partition(":")
            if not separator or not channel_user_id.strip() or not progressos_user_id.strip():
                raise ValueError(f"Invalid {cls.__name__} entry.")
            mappings[channel_user_id.strip()] = progressos_user_id.strip()
        return cls(mappings)

    def resolve(self, identity: ChannelUserIdentity) -> str:
        if identity.channel != self._channel:
            raise UserMappingError("Channel belum didukung.")
        progressos_user_id = self._mappings.get(identity.channel_user_id)
        if progressos_user_id is None:
            raise UserMappingError("User belum terhubung ke ProgressOS.")
        return progressos_user_id


class TelegramProgressOSUserMap(ChannelProgressOSUserMap):
    _channel = "telegram"


class WebChatProgressOSUserMap(ChannelProgressOSUserMap):
    _channel = "web_chat"
