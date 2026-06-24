import pytest
from pydantic import ValidationError

from progressos_bot.config import CAPTURE_INTENT_VALUES, Settings


def make_settings(**overrides: object) -> Settings:
    values = {
        "telegram_bot_token": "telegram-token",
        "groq_api_key": "groq-key",
        "progressos_base_url": "http://127.0.0.1:8000",
        "progressos_api_token": "progressos-token",
    }
    values.update(overrides)
    return Settings(**values)


def test_app_timezone_defaults_to_asia_jakarta() -> None:
    settings = make_settings()

    assert settings.app_timezone == "Asia/Jakarta"


def test_progressos_api_version_defaults_to_v1() -> None:
    settings = make_settings()

    assert settings.progressos_api_version == "v1"


def test_groq_structured_output_mode_defaults_to_off() -> None:
    settings = make_settings()

    assert settings.groq_structured_output_mode == "off"


def test_groq_structured_output_mode_accepts_best_effort() -> None:
    settings = make_settings(groq_structured_output_mode="best_effort")

    assert settings.groq_structured_output_mode == "best_effort"


def test_groq_structured_output_mode_accepts_strict() -> None:
    settings = make_settings(groq_structured_output_mode="strict")

    assert settings.groq_structured_output_mode == "strict"


def test_groq_structured_output_mode_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        make_settings(groq_structured_output_mode="json")


def test_progressos_api_version_must_use_version_label() -> None:
    with pytest.raises(ValidationError):
        make_settings(progressos_api_version="1")


def test_app_timezone_must_be_valid_iana_name() -> None:
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        make_settings(app_timezone="Mars/Base")


def test_app_default_language_defaults_to_indonesian() -> None:
    settings = make_settings()

    assert settings.app_default_language == "id"


def test_app_default_language_accepts_english() -> None:
    settings = make_settings(app_default_language="en")

    assert settings.app_default_language == "en"


def test_app_default_language_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        make_settings(app_default_language="unknown")


def test_capture_enabled_intents_default_to_all_capture_intents() -> None:
    settings = make_settings()

    assert settings.capture_enabled_intent_set() == frozenset(CAPTURE_INTENT_VALUES)


def test_capture_enabled_intents_are_parsed_from_csv() -> None:
    settings = make_settings(
        capture_enabled_intents="create_task, log_work, create_task",
    )

    assert settings.capture_enabled_intents == "create_task,log_work"
    assert settings.capture_enabled_intent_set() == frozenset({"create_task", "log_work"})


def test_capture_enabled_intents_must_be_known_intents() -> None:
    with pytest.raises(ValidationError, match="unknown intents"):
        make_settings(capture_enabled_intents="create_task,delete_everything")


def test_capture_max_input_chars_defaults_to_resource_safe_limit() -> None:
    settings = make_settings()

    assert settings.capture_max_input_chars == 2000


def test_capture_max_input_chars_is_capped_at_action_request_limit() -> None:
    with pytest.raises(ValidationError):
        make_settings(capture_max_input_chars=5001)


def test_capture_pre_parser_guard_mode_defaults_to_off() -> None:
    settings = make_settings()

    assert settings.capture_pre_parser_guard_mode == "off"


def test_capture_pre_parser_guard_mode_accepts_basic() -> None:
    settings = make_settings(capture_pre_parser_guard_mode="basic")

    assert settings.capture_pre_parser_guard_mode == "basic"


def test_capture_pre_parser_guard_mode_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        make_settings(capture_pre_parser_guard_mode="strict")
