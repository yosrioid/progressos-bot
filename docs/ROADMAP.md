# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 4: Read-Only Commands.

Current focus:

- Add read-only ProgressOS commands.
- Keep read responses concise and channel-friendly.
- Respect ProgressOS authorization on every read endpoint.
- Handle empty, unauthorized, and server-error responses safely.
- CI-gated Phase 4 slices.

## Next Milestones

1. Add `/learning_stats`.
2. Complete Phase 4 status after read-only commands are covered.
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
