# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 1: Telegram Capture MVP.

Current focus:

- Telegram polling adapter.
- Groq parser.
- Strict Pydantic validation.
- User confirmation before ProgressOS writes.
- CI-gated foundation.

## Next Milestones

1. Complete quick-capture mapping for all supported ProgressOS capture types.
2. Add idempotency keys and retry-safe HTTP behavior.
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
