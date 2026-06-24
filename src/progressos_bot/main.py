import asyncio
from dataclasses import dataclass

from progressos_bot.ai.groq_client import GroqParserClient
from progressos_bot.ai.parser import MessageParser
from progressos_bot.bot import ProgressOSTelegramBot
from progressos_bot.channels.web.route import WebChatHttpHandler
from progressos_bot.config import Settings, get_settings
from progressos_bot.core.admin import AdminInfoService, ConfigurationDiagnostics, VersionInfo
from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.core.identity import CaptureIdentityService
from progressos_bot.core.input_guard import PreParserInputGuard
from progressos_bot.core.rate_limit import InMemoryRateLimiter
from progressos_bot.core.read_commands import ReadCommandFlow
from progressos_bot.identity import (
    TelegramAllowlist,
    TelegramProgressOSUserMap,
    WebChatAllowlist,
    WebChatProgressOSUserMap,
)
from progressos_bot.logging import configure_logging
from progressos_bot.pending import InMemoryPendingActionStore, SQLitePendingActionStore
from progressos_bot.progressos_client import ProgressOSClient
from progressos_bot.retry_queue import SQLiteRetryQueue
from progressos_bot.version import get_package_version
from progressos_bot.webhook import (
    TelegramWebhookServer,
    WebhookServerConfig,
    run_webhook_application,
)


@dataclass
class CoreRuntime:
    progressos: ProgressOSClient
    capture_flow: CaptureFlow
    read_flow: ReadCommandFlow


def build_core_runtime(settings: Settings) -> CoreRuntime:
    groq = GroqParserClient(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        structured_output_mode=settings.groq_structured_output_mode,
    )
    parser = MessageParser(
        groq=groq,
        min_confidence=settings.ai_min_confidence,
        timezone_name=settings.app_timezone,
        default_language=settings.app_default_language,
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
        api_version=settings.progressos_api_version,
    )
    pending_store = None
    if settings.pending_store_path:
        pending_store = SQLitePendingActionStore(
            path=settings.pending_store_path,
            ttl_seconds=settings.confirmation_ttl_seconds,
        )

    pending = pending_store or InMemoryPendingActionStore(
        ttl_seconds=settings.confirmation_ttl_seconds
    )
    capture_flow = CaptureFlow(
        parser=parser,
        progressos=progressos,
        pending=pending,
        enabled_intents=settings.capture_enabled_intent_set(),
        max_input_chars=settings.capture_max_input_chars,
        input_guard=PreParserInputGuard(mode=settings.capture_pre_parser_guard_mode),
    )
    read_flow = ReadCommandFlow(progressos=progressos)

    return CoreRuntime(progressos=progressos, capture_flow=capture_flow, read_flow=read_flow)


def build_telegram_bot(settings: Settings, runtime: CoreRuntime) -> ProgressOSTelegramBot:
    return ProgressOSTelegramBot(
        token=settings.telegram_bot_token,
        parser=None,
        progressos=runtime.progressos,
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
                capture_pre_parser_guard_mode=settings.capture_pre_parser_guard_mode,
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
        capture_flow=runtime.capture_flow,
        read_flow=runtime.read_flow,
    )


def build_web_chat_handler(
    settings: Settings, runtime: CoreRuntime
) -> WebChatHttpHandler | None:
    if not settings.web_chat_path:
        return None
    identity_service = CaptureIdentityService(
        authorizer=WebChatAllowlist.from_csv(settings.web_chat_allowed_user_ids),
        progressos_user_resolver=WebChatProgressOSUserMap.from_csv(
            settings.web_chat_progressos_user_map
        ),
    )
    return WebChatHttpHandler(
        identity_service=identity_service,
        capture_flow=runtime.capture_flow,
        read_flow=runtime.read_flow,
    )


def run_polling(settings: Settings) -> None:
    runtime = build_core_runtime(settings)
    build_telegram_bot(settings, runtime).build_application().run_polling()


def run_webhook(settings: Settings) -> None:
    runtime = build_core_runtime(settings)
    application = build_telegram_bot(settings, runtime).build_application()
    web_chat_handler = build_web_chat_handler(settings, runtime)
    server = TelegramWebhookServer(
        config=WebhookServerConfig(
            host=settings.webhook_host,
            port=settings.webhook_port,
            webhook_path=settings.telegram_webhook_path,
            health_path=settings.health_path,
            readiness_path=settings.readiness_path,
            webhook_secret=settings.telegram_webhook_secret,
            web_chat_path=settings.web_chat_path,
            web_chat_secret=settings.web_chat_secret,
        ),
        application=application,
        web_chat_handler=web_chat_handler.handle if web_chat_handler else None,
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
