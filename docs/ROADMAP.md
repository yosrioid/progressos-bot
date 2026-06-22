# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 5: User Identity And Authorization.

Current focus:

- Move from one shared ProgressOS API token toward per-user authorization.
- Map Telegram user IDs to ProgressOS users.
- Block unknown or revoked users before submit/read actions.
- Keep ProgressOS as the final authorization gate.
- CI-gated Phase 5 slices.

## Next Milestones

1. Add channel user identity model.
2. Add Telegram allowlist bootstrap.
3. Add read-only ProgressOS commands.
4. Add per-user identity mapping and authorization.
5. Extract channel-neutral core services before adding another channel.

## Change Rule

Every new user-facing feature must update:

- Pydantic schemas.
- AI contract.
- ProgressOS API contract or research notes.
- Tests.
- Phase status when a milestone is completed.
