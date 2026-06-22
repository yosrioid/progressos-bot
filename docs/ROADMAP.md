# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 2: ProgressOS Quick Capture Completion.

Current focus:

- Quick-capture mapping from confirmed bot actions.
- Idempotency keys and retry-safe HTTP behavior.
- Safe validation, transient, and client error messages.
- Success responses that surface useful ProgressOS paths.
- CI-gated Phase 2 slices.

## Next Milestones

1. Finish Phase 2 quick-capture response and error coverage.
2. Add expanded capture intents for blocker, work log, daily progress, and learning.
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
