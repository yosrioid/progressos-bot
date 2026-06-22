from progressos_bot.ai.groq_client import GroqParserClient
from progressos_bot.ai.parser import MessageParser
from progressos_bot.bot import ProgressOSTelegramBot
from progressos_bot.config import get_settings
from progressos_bot.identity import TelegramAllowlist, TelegramProgressOSUserMap
from progressos_bot.logging import configure_logging
from progressos_bot.pending import SQLitePendingActionStore
from progressos_bot.progressos_client import ProgressOSClient


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    groq = GroqParserClient(api_key=settings.groq_api_key, model=settings.groq_model)
    parser = MessageParser(groq=groq, min_confidence=settings.ai_min_confidence)
    progressos = ProgressOSClient(
        base_url=str(settings.progressos_base_url),
        token=settings.progressos_api_token,
        endpoint=settings.progressos_assistant_endpoint,
        timeout_seconds=settings.http_timeout_seconds,
    )
    pending_store = None
    if settings.pending_store_path:
        pending_store = SQLitePendingActionStore(
            path=settings.pending_store_path,
            ttl_seconds=settings.confirmation_ttl_seconds,
        )

    bot = ProgressOSTelegramBot(
        token=settings.telegram_bot_token,
        parser=parser,
        progressos=progressos,
        authorizer=TelegramAllowlist.from_csv(
            settings.telegram_allowed_user_ids,
            revoked_value=settings.telegram_revoked_user_ids,
        ),
        user_map=TelegramProgressOSUserMap.from_csv(settings.telegram_progressos_user_map),
        confirmation_ttl_seconds=settings.confirmation_ttl_seconds,
        pending_store=pending_store,
    )
    bot.build_application().run_polling()


if __name__ == "__main__":
    main()
