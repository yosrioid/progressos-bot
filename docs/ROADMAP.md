# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 10: Product Hardening.

Current focus:

- Add rate limiting and abuse prevention around channel input.
- Add prompt injection regression cases.
- Normalize language and date handling for daily use.
- Add feature flags for risky intents.

## Next Milestones

1. Add per-user rate limiting before parser calls.
2. Add prompt injection test cases for unsupported or unsafe requests.
3. Add deterministic timezone-aware date handling.
4. Add admin-managed feature flags for capture intents.
5. Move identity mapping server-side when ProgressOS exposes it.

## Change Rule

Every new user-facing feature must update:

- Pydantic schemas.
- AI contract.
- ProgressOS API contract or research notes.
- Tests.
- Phase status when a milestone is completed.
