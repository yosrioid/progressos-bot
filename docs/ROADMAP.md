# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 3: Expanded Capture Intents.

Current focus:

- Add supported capture intents beyond task creation.
- Keep each intent behind strict Pydantic validation.
- Map confirmed intent payloads to ProgressOS quick-capture types.
- Keep user confirmation before every ProgressOS write.
- CI-gated Phase 3 slices.

## Next Milestones

1. Add `log_daily_progress` and verify quick-capture daily-progress writes.
2. Add `capture_learning` and verify quick-capture learning writes.
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
