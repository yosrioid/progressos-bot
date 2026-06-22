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
from progressos_bot.progressos_client import (
    ProgressOSClient,
    ProgressOSClientError,
    ProgressOSTransientError,
    ProgressOSValidationError,
)
from progressos_bot.schemas import ParsedAction, ProgressOSActionRequest

logger = logging.getLogger(__name__)

PendingActions = dict[str, tuple[str, ParsedAction]]


class ProgressOSTelegramBot:
    def __init__(
        self,
        token: str,
        parser: MessageParser,
        progressos: ProgressOSClient,
    ) -> None:
        self._token = token
        self._parser = parser
        self._progressos = progressos
        self._pending: PendingActions = {}

    def build_application(self) -> Any:
        app = Application.builder().token(self._token).build()
        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("cancel", self._handle_cancel))
        app.add_handler(CommandHandler("standup", self._handle_standup))
        app.add_handler(CallbackQueryHandler(self._handle_confirmation))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        return app

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.message is None:
            return
        await update.message.reply_text(
            "Kirim instruksi singkat. "
            "Saya akan ubah menjadi payload ProgressOS dan minta konfirmasi."
        )

    async def _handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.effective_user is None or update.message is None:
            return
        self._pending.pop(str(update.effective_user.id), None)
        await update.message.reply_text("Draft dibatalkan.")

    async def _handle_standup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.message is None:
            return

        try:
            response = await self._progressos.get_standup()
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

        await update.message.reply_text(response.to_user_message())

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.message is None or update.effective_user is None:
            return

        original_text = update.message.text or ""
        await update.message.reply_text("Memproses input...")

        try:
            action = await self._parser.parse(original_text)
        except Exception as exc:
            logger.exception("Failed to parse Telegram message")
            await update.message.reply_text(f"Input belum bisa diproses: {exc}")
            return

        if action.intent == "unsupported":
            await update.message.reply_text(action.user_confirmation_text)
            return

        user_key = str(update.effective_user.id)
        self._pending[user_key] = (original_text, action)

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Confirm", callback_data="confirm"),
                    InlineKeyboardButton("Cancel", callback_data="cancel"),
                ]
            ]
        )
        await update.message.reply_text(action.user_confirmation_text, reply_markup=keyboard)

    async def _handle_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        del context
        query = update.callback_query
        if query is None or update.effective_user is None or update.effective_chat is None:
            return

        await query.answer()
        user_key = str(update.effective_user.id)

        if query.data == "cancel":
            self._pending.pop(user_key, None)
            await query.edit_message_text("Draft dibatalkan.")
            return

        pending = self._pending.pop(user_key, None)
        if pending is None:
            await query.edit_message_text("Tidak ada draft aktif.")
            return

        original_text, action = pending
        request = ProgressOSActionRequest(
            source_user_id=str(update.effective_user.id),
            source_chat_id=str(update.effective_chat.id),
            original_text=original_text,
            parsed_action=action,
        )

        try:
            response = await self._progressos.submit_action(request)
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

        await query.edit_message_text(f"ProgressOS: {response.to_user_message()}")
