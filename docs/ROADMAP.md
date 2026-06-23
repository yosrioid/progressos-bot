# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 10: Product Hardening.

Current focus:

- Normalize language and date handling for daily use.
- Add feature flags for risky intents.
- Continue abuse prevention beyond per-user rate limiting.

## Next Milestones

1. Add admin-managed feature flags for capture intents.
2. Continue abuse prevention beyond per-user rate limiting.
3. Move identity mapping server-side when ProgressOS exposes it.

## Change Rule

Every new user-facing feature must update:

- Pydantic schemas.
- AI contract.
- ProgressOS API contract or research notes.
- Tests.
- Phase status when a milestone is completed.
