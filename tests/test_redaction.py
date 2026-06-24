from progressos_bot.observability.redaction import REDACTED, redact_mapping, redact_text


def test_redact_text_masks_bearer_tokens() -> None:
    value = "request failed with Authorization: Bearer sk_live_123456"

    redacted = redact_text(value)

    assert "sk_live_123456" not in redacted
    assert f"Bearer {REDACTED}" in redacted


def test_redact_text_masks_token_assignments() -> None:
    value = "telegram_token=123456:abcdef failed"

    redacted = redact_text(value)

    assert "123456:abcdef" not in redacted
    assert f"telegram_token={REDACTED}" in redacted


def test_redact_text_prioritizes_token_assignment_over_bearer_word() -> None:
    value = "Rotate bearer token=secret-value"

    redacted = redact_text(value)

    assert "secret-value" not in redacted
    assert redacted == f"Rotate bearer token={REDACTED}"


def test_redact_mapping_masks_secret_fields() -> None:
    redacted = redact_mapping(
        {
            "Authorization": "Bearer abc",
            "webhook_secret": "change-me",
            "status": "failed",
            "detail": "progressos_token=abc123",
        }
    )

    assert redacted["Authorization"] == REDACTED
    assert redacted["webhook_secret"] == REDACTED
    assert redacted["status"] == "failed"
    assert redacted["detail"] == f"progressos_token={REDACTED}"
