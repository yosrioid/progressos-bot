# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 7: Webhook Deployment.

Current focus:

- Add production-friendly webhook serving alongside local polling.
- Expose health and readiness checks.
- Keep Telegram webhook verification explicit.
- Preserve polling for local development.
- CI-gated Phase 7 slices.

## Next Milestones

1. Add webhook server entrypoint.
2. Add health and readiness endpoints.
3. Add graceful shutdown notes and deployment config.
4. Move identity mapping server-side when ProgressOS exposes it.
5. Extract channel-neutral core services before adding another channel.

## Change Rule

Every new user-facing feature must update:

- Pydantic schemas.
- AI contract.
- ProgressOS API contract or research notes.
- Tests.
- Phase status when a milestone is completed.
