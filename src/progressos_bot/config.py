from functools import lru_cache
from typing import Literal, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from progressos_bot.schemas import Intent

CAPTURE_INTENT_VALUES = tuple(intent for intent in get_args(Intent) if intent != "unsupported")
DEFAULT_CAPTURE_ENABLED_INTENTS = ",".join(CAPTURE_INTENT_VALUES)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(min_length=1)
    groq_api_key: str = Field(min_length=1)
    groq_model: str = "llama-3.3-70b-versatile"

    progressos_base_url: AnyHttpUrl
    progressos_api_token: str = Field(min_length=1)
    progressos_assistant_endpoint: str = "/api/v1/quick-capture"
    telegram_allowed_user_ids: str = ""
    telegram_revoked_user_ids: str = ""
    telegram_progressos_user_map: str = ""
    telegram_run_mode: Literal["polling", "webhook"] = "polling"
    telegram_webhook_url: AnyHttpUrl | None = None
    telegram_webhook_path: str = Field(
        default="/telegram/webhook",
        pattern=r"^/[A-Za-z0-9/_-]+$",
    )
    telegram_webhook_secret: str = ""
    webhook_host: str = "127.0.0.1"
    webhook_port: int = Field(default=8080, ge=1, le=65535)
    health_path: str = Field(default="/health", pattern=r"^/[A-Za-z0-9/_-]+$")
    readiness_path: str = Field(default="/ready", pattern=r"^/[A-Za-z0-9/_-]+$")
    confirmation_ttl_seconds: int = Field(default=900, gt=0)
    pending_store_path: str = ""
    retry_queue_path: str = ""
    retry_dead_letter_after_attempts: int = Field(default=5, gt=0)
    rate_limit_max_requests: int = Field(default=20, gt=0)
    rate_limit_window_seconds: int = Field(default=60, gt=0)
    capture_enabled_intents: str = DEFAULT_CAPTURE_ENABLED_INTENTS
    capture_max_input_chars: int = Field(default=2000, gt=0, le=5000)

    app_env: Literal["local", "staging", "production"] = "local"
    app_timezone: str = "Asia/Jakarta"
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    ai_min_confidence: float = Field(default=0.75, ge=0, le=1)
    http_timeout_seconds: float = Field(default=20, gt=0)

    @field_validator("app_timezone")
    @classmethod
    def validate_app_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("app_timezone must be a valid IANA timezone name") from exc
        return value

    @field_validator("capture_enabled_intents")
    @classmethod
    def validate_capture_enabled_intents(cls, value: str) -> str:
        tokens = cls._parse_capture_enabled_intents(value)
        unknown = sorted(set(tokens) - set(CAPTURE_INTENT_VALUES))
        if unknown:
            joined = ", ".join(unknown)
            raise ValueError(f"capture_enabled_intents contains unknown intents: {joined}")
        return ",".join(dict.fromkeys(tokens))

    def capture_enabled_intent_set(self) -> frozenset[str]:
        return frozenset(self._parse_capture_enabled_intents(self.capture_enabled_intents))

    @staticmethod
    def _parse_capture_enabled_intents(value: str) -> list[str]:
        return [token.strip() for token in value.split(",") if token.strip()]


@lru_cache
def get_settings() -> Settings:
    # BaseSettings populates required fields from environment variables at runtime.
    return Settings()  # type: ignore[call-arg]
