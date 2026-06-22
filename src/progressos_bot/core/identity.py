from dataclasses import dataclass

from progressos_bot.identity import (
    ChannelUserIdentity,
    ProgressOSUserResolver,
    UserAuthorizer,
)


@dataclass(frozen=True)
class ResolvedUserIdentity:
    channel_identity: ChannelUserIdentity
    progressos_user_id: str


class CaptureIdentityService:
    def __init__(
        self,
        *,
        authorizer: UserAuthorizer,
        progressos_user_resolver: ProgressOSUserResolver,
    ) -> None:
        self._authorizer = authorizer
        self._progressos_user_resolver = progressos_user_resolver

    def require_authorized(self, identity: ChannelUserIdentity) -> None:
        self._authorizer.require_authorized(identity)

    def resolve_for_capture(self, identity: ChannelUserIdentity) -> ResolvedUserIdentity:
        self.require_authorized(identity)
        progressos_user_id = self._progressos_user_resolver.resolve(identity)
        return ResolvedUserIdentity(
            channel_identity=identity,
            progressos_user_id=progressos_user_id,
        )
