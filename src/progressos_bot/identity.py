from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChannelUserIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Literal["telegram"]
    channel_user_id: str = Field(min_length=1)


class UserAuthorizationError(RuntimeError):
    pass


class TelegramAllowlist:
    def __init__(self, allowed_user_ids: Iterable[str]) -> None:
        self._allowed_user_ids = {
            user_id.strip() for user_id in allowed_user_ids if user_id.strip()
        }

    @classmethod
    def from_csv(cls, value: str) -> "TelegramAllowlist":
        return cls(value.split(","))

    def is_authorized(self, identity: ChannelUserIdentity) -> bool:
        return identity.channel == "telegram" and identity.channel_user_id in self._allowed_user_ids

    def require_authorized(self, identity: ChannelUserIdentity) -> None:
        if not self.is_authorized(identity):
            raise UserAuthorizationError("User belum diizinkan memakai bot ini.")
