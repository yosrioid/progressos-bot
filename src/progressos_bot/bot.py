import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from progressos_bot.ai.parser import MessageParser
from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.core.identity import CaptureIdentityService
from progressos_bot.core.read_commands import ReadCommandFlow
from progressos_bot.identity import (
    ChannelUserIdentity,
    TelegramAllowlist,
    TelegramProgressOSUserMap,
    UserAuthorizationError,
    UserMappingError,
)
from progressos_bot.pending import InMemoryPendingActionStore, PendingActionStore
from progressos_bot.progressos_client import (
    ProgressOSClient,
    ProgressOSClientError,
    ProgressOSTransientError,
    ProgressOSValidationError,
)

logger = logging.getLogger(__name__)


class ProgressOSTelegramBot:
    def __init__(
        self,
        token: str,
        parser: MessageParser,
        progressos: ProgressOSClient,
        authorizer: TelegramAllowlist,
        user_map: TelegramProgressOSUserMap,
        confirmation_ttl_seconds: int = 900,
        pending_store: PendingActionStore | None = None,
    ) -> None:
        self._token = token
        self._progressos = progressos
        self._authorizer = authorizer
        self._user_map = user_map
        self._identity = CaptureIdentityService(
            authorizer=authorizer,
            progressos_user_resolver=user_map,
        )
        self._read_flow = ReadCommandFlow(progressos=progressos)
        pending = pending_store or InMemoryPendingActionStore(
            ttl_seconds=confirmation_ttl_seconds
        )
        self._capture_flow = CaptureFlow(
            parser=parser,
            progressos=progressos,
            pending=pending,
        )

    def build_application(self) -> Any:
        app = Application.builder().token(self._token).build()
        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("cancel", self._handle_cancel))
        app.add_handler(CommandHandler("standup", self._handle_standup))
        app.add_handler(CommandHandler("dashboard", self._handle_dashboard))
        app.add_handler(CommandHandler("search", self._handle_search))
        app.add_handler(CommandHandler("overdue", self._handle_overdue))
        app.add_handler(CommandHandler("kanban", self._handle_kanban))
        app.add_handler(CommandHandler("learning_stats", self._handle_learning_stats))
        app.add_handler(CallbackQueryHandler(self._handle_confirmation))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        return app

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.message is None:
            return
        if not await self._authorize_message(update):
            return
        await update.message.reply_text(
            "Kirim instruksi singkat. "
            "Saya akan ubah menjadi payload ProgressOS dan minta konfirmasi."
        )

    async def _handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.effective_user is None or update.message is None:
            return
        if not await self._authorize_message(update):
            return
        self._capture_flow.cancel_capture(user_key=str(update.effective_user.id))
        await update.message.reply_text("Draft dibatalkan.")

    async def _handle_standup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.message is None:
            return
        if not await self._authorize_mapped_message(update):
            return

        try:
            result = await self._read_flow.standup()
        except ProgressOSTransientError as exc:
            logger.warning("Transient ProgressOS standup failure")
            await update.message.reply_text(str(exc))
            return
        except ProgressOSClientError as exc:
            logger.warning("ProgressOS standup client failure")
            await update.message.reply_text(str(exc))
            return
        except Exception as exc:
            logger.exception("Failed to fetch ProgressOS standup")
            await update.message.reply_text(f"Gagal mengambil standup: {exc}")
            return

        await update.message.reply_text(result.user_message)

    async def _handle_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.message is None:
            return
        if not await self._authorize_mapped_message(update):
            return

        try:
            result = await self._read_flow.dashboard()
        except ProgressOSTransientError as exc:
            logger.warning("Transient ProgressOS dashboard failure")
            await update.message.reply_text(str(exc))
            return
        except ProgressOSClientError as exc:
            logger.warning("ProgressOS dashboard client failure")
            await update.message.reply_text(str(exc))
            return
        except Exception as exc:
            logger.exception("Failed to fetch ProgressOS dashboard")
            await update.message.reply_text(f"Gagal mengambil dashboard: {exc}")
            return

        await update.message.reply_text(result.user_message)

    async def _handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None:
            return
        if not await self._authorize_mapped_message(update):
            return

        args = context.args or []
        query = " ".join(args).strip()
        if not query:
            await update.message.reply_text("Kirim /search <query>.")
            return
        if len(query) > 120:
            await update.message.reply_text("Query pencarian maksimal 120 karakter.")
            return

        try:
            result = await self._read_flow.search(query=query)
        except ProgressOSTransientError as exc:
            logger.warning("Transient ProgressOS search failure")
            await update.message.reply_text(str(exc))
            return
        except ProgressOSClientError as exc:
            logger.warning("ProgressOS search client failure")
            await update.message.reply_text(str(exc))
            return
        except Exception as exc:
            logger.exception("Failed to search ProgressOS")
            await update.message.reply_text(f"Gagal mencari di ProgressOS: {exc}")
            return

        await update.message.reply_text(result.user_message)

    async def _handle_overdue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.message is None:
            return
        if not await self._authorize_mapped_message(update):
            return

        try:
            result = await self._read_flow.overdue()
        except ProgressOSTransientError as exc:
            logger.warning("Transient ProgressOS overdue failure")
            await update.message.reply_text(str(exc))
            return
        except ProgressOSClientError as exc:
            logger.warning("ProgressOS overdue client failure")
            await update.message.reply_text(str(exc))
            return
        except Exception as exc:
            logger.exception("Failed to fetch ProgressOS overdue tasks")
            await update.message.reply_text(f"Gagal mengambil task overdue: {exc}")
            return

        await update.message.reply_text(result.user_message)

    async def _handle_kanban(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.message is None:
            return
        if not await self._authorize_mapped_message(update):
            return

        try:
            result = await self._read_flow.kanban()
        except ProgressOSTransientError as exc:
            logger.warning("Transient ProgressOS kanban failure")
            await update.message.reply_text(str(exc))
            return
        except ProgressOSClientError as exc:
            logger.warning("ProgressOS kanban client failure")
            await update.message.reply_text(str(exc))
            return
        except Exception as exc:
            logger.exception("Failed to fetch ProgressOS kanban")
            await update.message.reply_text(f"Gagal mengambil kanban: {exc}")
            return

        await update.message.reply_text(result.user_message)

    async def _handle_learning_stats(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        del context
        if update.message is None:
            return
        if not await self._authorize_mapped_message(update):
            return

        try:
            result = await self._read_flow.learning_stats()
        except ProgressOSTransientError as exc:
            logger.warning("Transient ProgressOS learning stats failure")
            await update.message.reply_text(str(exc))
            return
        except ProgressOSClientError as exc:
            logger.warning("ProgressOS learning stats client failure")
            await update.message.reply_text(str(exc))
            return
        except Exception as exc:
            logger.exception("Failed to fetch ProgressOS learning stats")
            await update.message.reply_text(f"Gagal mengambil learning stats: {exc}")
            return

        await update.message.reply_text(result.user_message)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.message is None or update.effective_user is None:
            return
        if not await self._authorize_message(update):
            return

        original_text = update.message.text or ""
        await update.message.reply_text("Memproses input...")

        try:
            draft = await self._capture_flow.begin_capture(
                user_key=str(update.effective_user.id),
                original_text=original_text,
            )
        except Exception as exc:
            logger.exception("Failed to parse Telegram message")
            await update.message.reply_text(f"Input belum bisa diproses: {exc}")
            return

        if draft.status == "unsupported":
            await update.message.reply_text(draft.user_message)
            return

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Confirm", callback_data="confirm"),
                    InlineKeyboardButton("Cancel", callback_data="cancel"),
                ]
            ]
        )
        await update.message.reply_text(draft.user_message, reply_markup=keyboard)

    async def _handle_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        del context
        query = update.callback_query
        if query is None or update.effective_user is None or update.effective_chat is None:
            return

        await query.answer()
        identity = ChannelUserIdentity(
            channel="telegram",
            channel_user_id=str(update.effective_user.id),
        )

        user_key = str(update.effective_user.id)

        if query.data == "cancel":
            self._capture_flow.cancel_capture(user_key=user_key)
            await query.edit_message_text("Draft dibatalkan.")
            return
        try:
            resolved_identity = self._identity.resolve_for_capture(identity)
        except (UserAuthorizationError, UserMappingError) as exc:
            await query.edit_message_text(str(exc))
            return

        try:
            result = await self._capture_flow.submit_confirmed_capture(
                user_key=user_key,
                source_user_id=str(update.effective_user.id),
                source_chat_id=str(update.effective_chat.id),
                progressos_user_id=resolved_identity.progressos_user_id,
            )
        except ProgressOSValidationError as exc:
            logger.info("ProgressOS rejected action validation")
            await query.edit_message_text(f"ProgressOS menolak input: {exc.response.message}")
            return
        except ProgressOSTransientError as exc:
            logger.warning("Transient ProgressOS failure")
            await query.edit_message_text(str(exc))
            return
        except ProgressOSClientError as exc:
            logger.warning("ProgressOS client failure")
            await query.edit_message_text(str(exc))
            return
        except Exception as exc:
            logger.exception("Failed to submit action to ProgressOS")
            await query.edit_message_text(f"Gagal mengirim ke ProgressOS: {exc}")
            return

        if not result.submitted:
            await query.edit_message_text(result.user_message)
            return

        await query.edit_message_text(f"ProgressOS: {result.user_message}")

    async def _authorize_message(self, update: Update) -> bool:
        if update.message is None:
            return False
        if update.effective_user is None:
            await update.message.reply_text("Identitas Telegram tidak tersedia.")
            return False

        identity = ChannelUserIdentity(
            channel="telegram",
            channel_user_id=str(update.effective_user.id),
        )
        try:
            self._identity.require_authorized(identity)
        except UserAuthorizationError as exc:
            await update.message.reply_text(str(exc))
            return False
        return True

    async def _authorize_mapped_message(self, update: Update) -> bool:
        if not await self._authorize_message(update):
            return False
        if update.message is None or update.effective_user is None:
            return False

        identity = ChannelUserIdentity(
            channel="telegram",
            channel_user_id=str(update.effective_user.id),
        )
        try:
            self._identity.resolve_for_capture(identity)
        except (UserAuthorizationError, UserMappingError) as exc:
            await update.message.reply_text(str(exc))
            return False
        return True
