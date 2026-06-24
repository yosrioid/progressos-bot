# Next Version Phases

This document captures research and candidate phases after `v0.1.0`.
The existing `docs/PHASES.md` remains the source of truth for completed `v0.1.0`
scope. New work should use this document to select the next small release slices.

## Research Snapshot

Date: 2026-06-23.

Current repo baseline:

- `v0.1.0` is released.
- Phases 0-9 are complete.
- Phase 10 is complete for bot-owned scope.
- Telegram remains the first production channel.
- ProgressOS remains the source of truth for authorization and writes.
- The bot still uses `TELEGRAM_PROGRESSOS_USER_MAP` until ProgressOS exposes
  server-side channel identity resolution.
- The parser currently asks Groq for a JSON object and validates it locally with
  strict Pydantic schemas.

External references reviewed:

- Groq Structured Outputs:
  https://console.groq.com/docs/structured-outputs
- Groq Supported Models:
  https://console.groq.com/docs/models
- OWASP Top 10 for LLM Applications:
  https://owasp.org/www-project-top-10-for-large-language-model-applications/
- GitHub Actions secure use:
  https://docs.github.com/en/actions/reference/security/secure-use
- Telegram Mini Apps:
  https://core.telegram.org/bots/webapps

## Key Gaps

1. Model output reliability can be stronger.
   Groq supports Structured Outputs with JSON Schema. Strict mode is documented as
   constrained decoding with exact schema adherence, but it has limited model support.
   The current bot still relies on prompt instructions plus `json.loads`, then Pydantic.

2. Model selection is static.
   `GROQ_MODEL` defaults to `llama-3.3-70b-versatile`. Groq's current production model
   list includes GPT OSS 20B and 120B in addition to Llama models. The bot needs an
   evaluation harness before changing the default model.

3. Security posture is good for `v0.1.0`, but can be more systematic.
   OWASP calls out prompt injection, insecure output handling, model denial of service,
   sensitive information disclosure, excessive agency, and supply-chain vulnerabilities
   as LLM application risks. The bot already addresses several of these, but lacks a
   named LLM security regression suite mapped to those categories.

4. Identity remains the largest product dependency.
   The bot still owns a bootstrap Telegram-to-ProgressOS map. Production authorization
   should move to a ProgressOS-owned identity resolution endpoint when available.

5. Telegram UX can become more reliable for structured capture.
   Free-form text is fast, but Telegram Mini Apps can provide mobile-first structured
   inputs, theme-aware UI, and `sendData` back to the bot for complex capture forms.

6. Production operations can improve.
   Retry queue and dead-letter storage exist, but operators do not yet have command-line
   or admin-command tooling to inspect, requeue, or export dead-letter entries safely.

## Phase 11: Structured Model Contract

Status: in progress.

Goal: reduce malformed model output and make model changes measurable.

Features:

- Generate JSON Schema from the existing parser schemas - started.
- Add Groq `response_format` support for structured outputs - started.
- Support strict mode when the configured model supports it.
- Fall back to best-effort structured output or JSON object parsing when strict mode is
  unavailable.
- Add an offline parser evaluation fixture set for Indonesian and English messages -
  started.
- Track parse outcome metrics by model, intent, language, and failure category.

Current implementation slice:

- `GROQ_STRUCTURED_OUTPUT_MODE` selects `off`, `best_effort`, or `strict`.
- The Groq parser client sends `response_format` when structured output is enabled.
- The default remains `off` until evaluation results justify changing behavior.
- `progressos-bot-eval-parser` evaluates offline parser output fixtures without calling
  Groq.
- Evaluation summaries include pass/fail breakdowns by intent, language, and failure
  category.

Acceptance criteria:

- Existing parser validation still rejects unknown fields and wrong payload shapes.
- Tests cover strict structured output request construction.
- Tests cover fallback behavior when structured output is disabled.
- Evaluation fixtures include supported, ambiguous, unsafe, and prompt-injection cases.
- Default model is not changed until evaluation results are documented.

Suggested release: `v0.2.0`.

## Phase 12: LLM Security Regression Program

Status: in progress.

Goal: make LLM-specific risks explicit, testable, and repeatable.

Features:

- Map bot behavior to OWASP LLM risk categories relevant to this project - started:
  prompt injection, insecure output handling, model denial of service, sensitive
  information disclosure, supply-chain vulnerabilities, and excessive agency.
- Add prompt-injection fixture packs for Indonesian, English, mixed-language, and
  copy-pasted system-prompt attacks - started.
- Add tests proving the model cannot enable disabled intents - started.
- Add tests proving parser output cannot add unauthorized API targets, headers, or
  ProgressOS paths - started.
- Add optional pre-parser guard mode for high-risk deployments - started.
- Document operational guidance for secret rotation and model-key scope - started.

Acceptance criteria:

- Security regression tests run in CI.
- Unsafe messages remain unsupported or validation failures.
- No test fixture can bypass local validation or user confirmation.
- Docs clearly state what is handled by the bot and what remains ProgressOS-owned.

Suggested release: `v0.2.x`.

Current implementation slice:

- `tests/fixtures/llm_security_evaluation.json` covers prompt injection, sensitive
  information disclosure, excessive agency, insecure output handling, and model denial of
  service.
- Parser evaluation summaries include `by_risk_category` for security fixture reporting.
- Capture flow regressions prove model output for disabled intents creates no pending
  draft and no ProgressOS submit.
- Payload validation tests reject parser-supplied API URLs, headers, endpoints, and
  ProgressOS paths.
- `CAPTURE_PRE_PARSER_GUARD_MODE=basic` blocks obvious prompt-injection and
  secret-exfiltration text before parser calls.
- `docs/SECURITY.md` documents secret rotation steps, incident triggers, and model-key
  scope guidance.

## Phase 13: ProgressOS-Owned Identity Resolution

Status: proposed, blocked by ProgressOS API support.

Goal: remove local Telegram-to-ProgressOS bootstrap mapping from production deployments.

Required ProgressOS contract:

- A server-side endpoint that resolves stable channel identity to a ProgressOS user.
- Authorization semantics for read commands and quick-capture writes.
- Safe errors for unknown, revoked, or unmapped channel users.
- Audit fields accepted or generated by ProgressOS for channel source metadata.

Bot features after the contract exists:

- Replace `TELEGRAM_PROGRESSOS_USER_MAP` with a ProgressOS identity lookup client.
- Cache identity lookups with a short TTL and safe invalidation.
- Keep local env mapping only for local development or emergency fallback.
- Add tests for known, unknown, revoked, unmapped, and ProgressOS-error states.

Acceptance criteria:

- Production mode can reject local bootstrap mapping.
- ProgressOS remains the final authorization gate.
- Read and write flows use the same identity resolution path.

Suggested release: `v0.3.0`, depending on ProgressOS readiness.

## Phase 14: Guided Capture UX

Status: proposed.

Goal: improve capture quality when free-form text is too ambiguous.

Candidate features:

- Telegram Mini App or guided inline flow for structured capture.
- Date, duration, project, priority, and severity pickers.
- Draft preview before confirmation.
- "Edit draft" flow before submission.
- Reuse the same `CaptureFlow` and ProgressOS client; do not duplicate business logic in
  channel adapters.

Acceptance criteria:

- Free-form text still works.
- Guided capture produces the same strict `ParsedAction` shape.
- Draft edits still require final confirmation.
- Mini App or guided flow never bypasses authorization, validation, or ProgressOS.

Suggested release: `v0.3.x`.

## Phase 15: Operator Recovery Tools

Status: proposed.

Goal: make production failures easier to inspect and recover without database edits.

Features:

- Admin command or CLI command to list retry queue counts.
- Admin command or CLI command to inspect dead-letter metadata without secrets.
- Requeue or discard dead-letter entries with explicit operator confirmation.
- Export redacted diagnostic bundle for a correlation ID.
- Document production runbook for retries, dead letters, webhook health, and dependency
  outage triage.

Acceptance criteria:

- Operators can recover transient ProgressOS outages without manual SQLite edits.
- Dead-letter inspection never prints bearer tokens or raw headers.
- Requeue preserves original idempotency key unless operator explicitly discards it.

Suggested release: `v0.4.0`.

## Phase 16: Channel Expansion

Status: proposed.

Goal: prove the channel-neutral core with a second real channel.

Candidate channels:

- Slack for workspace users.
- Discord for community/team channels.
- Web chat for ProgressOS dashboard embedding.

Rules:

- Reuse `CaptureFlow`, `ReadCommandFlow`, parser schemas, identity service, and
  ProgressOS client.
- Add only channel adapter code and channel-specific formatting.
- Do not add channel-specific business rules.

Acceptance criteria:

- One new channel can capture and confirm at least `create_task` and `log_work`.
- Read-only commands work with that channel's identity resolution path.
- Tests cover the adapter without Telegram-specific classes.

Suggested release: `v0.4.x` or later.

## Phase 17: Release And Supply-Chain Hardening

Status: proposed.

Goal: reduce release and CI supply-chain risk.

Features:

- Set explicit minimal `permissions` in GitHub Actions workflows.
- Evaluate pinning third-party GitHub Actions to full commit SHAs.
- Add dependency audit workflow or documented dependency review process.
- Add a release checklist for tag target, changelog, CI result, and rollback notes.
- Add optional signed tags if the release environment supports them.

Acceptance criteria:

- CI has least-privilege `GITHUB_TOKEN` permissions.
- Release checklist is followed before every tag.
- Dependency updates are visible before release.

Suggested release: `v0.2.x`.

## Recommended Order

1. Phase 11 - Structured Model Contract.
2. Phase 12 - LLM Security Regression Program.
3. Phase 17 - Release And Supply-Chain Hardening.
4. Phase 15 - Operator Recovery Tools.
5. Phase 13 - ProgressOS-Owned Identity Resolution, once the ProgressOS API exists.
6. Phase 14 or Phase 16 depending on whether UX or channel reach matters more next.

The best immediate next slice is Phase 11 because it reduces the riskiest live dependency:
model output shape. It also creates the evaluation harness needed before changing the
default model.
