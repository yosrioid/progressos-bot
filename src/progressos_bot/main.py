import asyncio

from progressos_bot.ai.groq_client import GroqParserClient
from progressos_bot.ai.parser import MessageParser
from progressos_bot.bot import ProgressOSTelegramBot
from progressos_bot.config import Settings, get_settings
from progressos_bot.core.admin import AdminInfoService, ConfigurationDiagnostics, VersionInfo
from progressos_bot.core.rate_limit import InMemoryRateLimiter
from progressos_bot.identity import TelegramAllowlist, TelegramProgressOSUserMap
from progressos_bot.logging import configure_logging
from progressos_bot.pending import SQLitePendingActionStore
from progressos_bot.progressos_client import ProgressOSClient
from progressos_bot.retry_queue import SQLiteRetryQueue
from progressos_bot.version import get_package_version
from progressos_bot.webhook import (
    TelegramWebhookServer,
    WebhookServerConfig,
    run_webhook_application,
)


def build_telegram_bot(settings: Settings) -> ProgressOSTelegramBot:
    groq = GroqParserClient(api_key=settings.groq_api_key, model=settings.groq_model)
    parser = MessageParser(
        groq=groq,
        min_confidence=settings.ai_min_confidence,
        timezone_name=settings.app_timezone,
    )
    retry_queue = None
    if settings.retry_queue_path:
        retry_queue = SQLiteRetryQueue(
            path=settings.retry_queue_path,
            dead_letter_after_attempts=settings.retry_dead_letter_after_attempts,
        )
    progressos = ProgressOSClient(
        base_url=str(settings.progressos_base_url),
        token=settings.progressos_api_token,
        endpoint=settings.progressos_assistant_endpoint,
        timeout_seconds=settings.http_timeout_seconds,
        retry_queue=retry_queue,
    )
    pending_store = None
    if settings.pending_store_path:
        pending_store = SQLitePendingActionStore(
            path=settings.pending_store_path,
            ttl_seconds=settings.confirmation_ttl_seconds,
        )

    return ProgressOSTelegramBot(
        token=settings.telegram_bot_token,
        parser=parser,
        progressos=progressos,
        authorizer=TelegramAllowlist.from_csv(
            settings.telegram_allowed_user_ids,
            revoked_value=settings.telegram_revoked_user_ids,
        ),
        user_map=TelegramProgressOSUserMap.from_csv(settings.telegram_progressos_user_map),
        admin_info=AdminInfoService(
            version_info=VersionInfo(
                app_name="progressos-bot",
                app_version=get_package_version(),
                app_env=settings.app_env,
                run_mode=settings.telegram_run_mode,
                log_format=settings.log_format,
            ),
            diagnostics=ConfigurationDiagnostics(
                app_env=settings.app_env,
                run_mode=settings.telegram_run_mode,
                log_format=settings.log_format,
                capture_enabled_intents=settings.capture_enabled_intent_set(),
                pending_store_enabled=bool(settings.pending_store_path),
                retry_queue_enabled=bool(settings.retry_queue_path),
                allowlist_configured=bool(settings.telegram_allowed_user_ids.strip()),
                user_map_configured=bool(settings.telegram_progressos_user_map.strip()),
                webhook_secret_configured=bool(settings.telegram_webhook_secret),
            ),
        ),
        rate_limiter=InMemoryRateLimiter(
            max_requests=settings.rate_limit_max_requests,
            window_seconds=settings.rate_limit_window_seconds,
        ),
        confirmation_ttl_seconds=settings.confirmation_ttl_seconds,
        pending_store=pending_store,
        enabled_capture_intents=settings.capture_enabled_intent_set(),
        capture_max_input_chars=settings.capture_max_input_chars,
    )


def run_polling(settings: Settings) -> None:
    build_telegram_bot(settings).build_application().run_polling()


def run_webhook(settings: Settings) -> None:
    application = build_telegram_bot(settings).build_application()
    server = TelegramWebhookServer(
        config=WebhookServerConfig(
            host=settings.webhook_host,
            port=settings.webhook_port,
            webhook_path=settings.telegram_webhook_path,
            health_path=settings.health_path,
            readiness_path=settings.readiness_path,
            webhook_secret=settings.telegram_webhook_secret,
        ),
        application=application,
    )
    webhook_url = str(settings.telegram_webhook_url) if settings.telegram_webhook_url else None
    asyncio.run(
        run_webhook_application(
            application=application,
            server=server,
            webhook_url=webhook_url,
            webhook_secret=settings.telegram_webhook_secret,
        )
    )


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, log_format=settings.log_format)

    if settings.telegram_run_mode == "webhook":
        run_webhook(settings)
        return

    run_polling(settings)


if __name__ == "__main__":
    main()
