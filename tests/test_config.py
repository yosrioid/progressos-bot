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


def test_app_timezone_must_be_valid_iana_name() -> None:
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        make_settings(app_timezone="Mars/Base")


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
