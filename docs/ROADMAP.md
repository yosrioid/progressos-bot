# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Phase

Phase 9: Observability And Admin Tools.

Current focus:

- Add request correlation IDs.
- Add metrics for parse, confirmation, submit, and dependency failures.
- Add safe admin diagnostics without exposing secrets.
- Keep logging and diagnostic output secret-safe.

## Next Milestones

1. Add request correlation IDs across capture and read flows.
2. Add metrics counters for key bot outcomes.
3. Add a safe version/build info command.
4. Add a safe configuration diagnostic command.
5. Move identity mapping server-side when ProgressOS exposes it.

## Change Rule

Every new user-facing feature must update:

- Pydantic schemas.
- AI contract.
- ProgressOS API contract or research notes.
- Tests.
- Phase status when a milestone is completed.
