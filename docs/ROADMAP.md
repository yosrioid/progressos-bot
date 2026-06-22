# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 6: Persistence And Operational Reliability.

Current focus:

- Make pending confirmations safer and restart-aware.
- Expire stale confirmation drafts before submit.
- Persist pending confirmations when configured.
- Queue exhausted transient writes with their original idempotency key.
- Move repeated retry failures to dead-letter storage.
- CI-gated Phase 6 slices.

## Next Milestones

1. Add structured operational logs.
2. Move identity mapping server-side when ProgressOS exposes it.
3. Extract channel-neutral core services before adding another channel.

## Change Rule

Every new user-facing feature must update:

- Pydantic schemas.
- AI contract.
- ProgressOS API contract or research notes.
- Tests.
- Phase status when a milestone is completed.
