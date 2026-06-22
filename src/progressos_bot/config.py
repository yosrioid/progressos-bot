from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(min_length=1)
    groq_api_key: str = Field(min_length=1)
    groq_model: str = "llama-3.3-70b-versatile"

    progressos_base_url: AnyHttpUrl
    progressos_api_token: str = Field(min_length=1)
    progressos_assistant_endpoint: str = "/api/v1/quick-capture"
    telegram_allowed_user_ids: str = ""

    app_env: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"
    ai_min_confidence: float = Field(default=0.75, ge=0, le=1)
    http_timeout_seconds: float = Field(default=20, gt=0)


@lru_cache
def get_settings() -> Settings:
    # BaseSettings populates required fields from environment variables at runtime.
    return Settings()  # type: ignore[call-arg]
