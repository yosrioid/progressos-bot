# Roadmap

The detailed phase plan lives in [Product Phases](PHASES.md).

## Current Status

Phase 10 bot-owned hardening is complete. `v0.1.0` has been released.

Current focus:

- Keep ProgressOS as the authorization source of truth.
- Wait for a ProgressOS-owned server-side identity resolution contract.
- Plan the next version from [Next Version Phases](NEXT_PHASES.md).

## Next Milestones

1. Add a structured model contract and model evaluation harness.
2. Expand LLM security regression coverage.
3. Harden release and CI supply-chain controls.
4. Move identity mapping server-side when ProgressOS exposes it.

No bot-owned Phase 10 milestone is currently open. New work should use Phase 11 and later.

## Change Rule

Every new user-facing feature must update:

- Pydantic schemas.
- AI contract.
- ProgressOS API contract or research notes.
- Tests.
- Phase status when a milestone is completed.
