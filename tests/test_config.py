import pytest
from pydantic import ValidationError

from progressos_bot.config import Settings


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
