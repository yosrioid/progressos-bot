# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 8: Multi-Channel Core.

Current focus:

- Extract channel-neutral core contracts before adding another adapter.
- Keep Telegram behavior passing through the extraction.
- Move parsing, validation, confirmation state, and ProgressOS submission into reusable
  services.
- Add core-flow tests that do not depend on Telegram-specific classes.

## Next Milestones

1. Define channel-neutral message, user, confirmation, and adapter contracts.
2. Extract reusable capture flow from the Telegram adapter.
3. Rewire Telegram to use the shared core flow.
4. Add non-Telegram core-flow tests.
5. Move identity mapping server-side when ProgressOS exposes it.

## Change Rule

Every new user-facing feature must update:

- Pydantic schemas.
- AI contract.
- ProgressOS API contract or research notes.
- Tests.
- Phase status when a milestone is completed.
