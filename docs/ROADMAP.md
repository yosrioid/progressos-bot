# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 6: Persistence And Operational Reliability.

Current focus:

- Make pending confirmations safer and restart-aware.
- Expire stale confirmation drafts before submit.
- Add persistent pending action storage.
- Keep idempotent writes recoverable.
- CI-gated Phase 6 slices.

## Next Milestones

1. Add persistent pending action store.
2. Add pending action rehydration after restart.
3. Add idempotency-aware retry queue.
4. Add dead-letter handling for repeated failures.
5. Add structured operational logs.
6. Move identity mapping server-side when ProgressOS exposes it.
7. Extract channel-neutral core services before adding another channel.

## Change Rule

Every new user-facing feature must update:

- Pydantic schemas.
- AI contract.
- ProgressOS API contract or research notes.
- Tests.
- Phase status when a milestone is completed.
