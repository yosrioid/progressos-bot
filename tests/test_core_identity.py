from dataclasses import dataclass

import pytest

from progressos_bot.core.identity import CaptureIdentityService
from progressos_bot.identity import (
    ChannelUserIdentity,
    UserAuthorizationError,
    UserMappingError,
)


@dataclass
class FakeAuthorizer:
    authorized: bool = True

    def require_authorized(self, identity: ChannelUserIdentity) -> None:
        del identity
        if not self.authorized:
            raise UserAuthorizationError("not authorized")


@dataclass
class FakeResolver:
    progressos_user_id: str | None = "77"

    def resolve(self, identity: ChannelUserIdentity) -> str:
        del identity
        if self.progressos_user_id is None:
            raise UserMappingError("not mapped")
        return self.progressos_user_id


def test_capture_identity_service_resolves_authorized_user() -> None:
    identity = ChannelUserIdentity(channel="discord", channel_user_id="user-1")
    service = CaptureIdentityService(
        authorizer=FakeAuthorizer(),
        progressos_user_resolver=FakeResolver(progressos_user_id="99"),
    )

    resolved = service.resolve_for_capture(identity)

    assert resolved.channel_identity == identity
    assert resolved.progressos_user_id == "99"


def test_capture_identity_service_rejects_unauthorized_user_before_mapping() -> None:
    identity = ChannelUserIdentity(channel="telegram", channel_user_id="123")
    service = CaptureIdentityService(
        authorizer=FakeAuthorizer(authorized=False),
        progressos_user_resolver=FakeResolver(progressos_user_id="77"),
    )

    with pytest.raises(UserAuthorizationError):
        service.resolve_for_capture(identity)


def test_capture_identity_service_rejects_unmapped_user() -> None:
    identity = ChannelUserIdentity(channel="telegram", channel_user_id="123")
    service = CaptureIdentityService(
        authorizer=FakeAuthorizer(),
        progressos_user_resolver=FakeResolver(progressos_user_id=None),
    )

    with pytest.raises(UserMappingError):
        service.resolve_for_capture(identity)
