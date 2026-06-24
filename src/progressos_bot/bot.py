import logging
from collections.abc import Collection
from datetime import date
from typing import Any

from pydantic import ValidationError
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
from progressos_bot.channels.base import ChannelMessage, ChannelUser
from progressos_bot.channels.telegram.adapter import TelegramChannelAdapter
from progressos_bot.core.admin import AdminInfoService
from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.core.guided_capture import (
    GuidedCaptureChannelFlow,
    GuidedCaptureDraft,
    GuidedCaptureField,
    GuidedCaptureIntent,
    guided_capture_fields,
)
from progressos_bot.core.identity import CaptureIdentityService
from progressos_bot.core.input_guard import InputGuard
from progressos_bot.core.rate_limit import NoopRateLimiter, RateLimiter
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

GUIDED_CAPTURE_INTENTS: tuple[GuidedCaptureIntent, ...] = (
    "create_task",
    "create_blocker",
    "log_work",
    "log_daily_progress",
    "capture_learning",
)


def _user_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    return getattr(context, "user_data", None)


class ProgressOSTelegramBot:
    def __init__(
        self,
        token: str,
        parser: MessageParser | None,
        progressos: ProgressOSClient,
        authorizer: TelegramAllowlist,
        user_map: TelegramProgressOSUserMap,
        admin_info: AdminInfoService,
        rate_limiter: RateLimiter | None = None,
        confirmation_ttl_seconds: int = 900,
        pending_store: PendingActionStore | None = None,
        enabled_capture_intents: Collection[str] | None = None,
        capture_max_input_chars: int = 2000,
        capture_input_guard: InputGuard | None = None,
        capture_flow: CaptureFlow | None = None,
        read_flow: ReadCommandFlow | None = None,
    ) -> None:
        self._token = token
        self._progressos = progressos
        self._authorizer = authorizer
        self._user_map = user_map
        self._admin_info = admin_info
        self._rate_limiter = rate_limiter or NoopRateLimiter()
        self._identity = CaptureIdentityService(
            authorizer=authorizer,
            progressos_user_resolver=user_map,
        )
        self._read_flow = read_flow or ReadCommandFlow(progressos=progressos)
        if capture_flow is not None:
            self._capture_flow = capture_flow
        else:
            if parser is None:
                raise ValueError("parser is required when capture_flow is not provided.")
            pending = pending_store or InMemoryPendingActionStore(
                ttl_seconds=confirmation_ttl_seconds
            )
            self._capture_flow = CaptureFlow(
                parser=parser,
                progressos=progressos,
                pending=pending,
                enabled_intents=enabled_capture_intents,
                max_input_chars=capture_max_input_chars,
                input_guard=capture_input_guard,
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
        app.add_handler(CommandHandler("version", self._handle_version))
        app.add_handler(CommandHandler("diagnostics", self._handle_diagnostics))
        app.add_handler(CommandHandler("guided", self._handle_guided_start))
        app.add_handler(CallbackQueryHandler(self._handle_guided_callback, pattern=r"^guided:"))
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
        if update.effective_user is None or update.message is None:
            return
        if not await self._authorize_message(update):
            return
        user_id = update.effective_user.id
        self._capture_flow.cancel_capture(user_key=str(user_id))
        self._capture_flow.cancel_capture(user_key=f"telegram:{user_id}")
        user_data = _user_data(context)
        if user_data is not None:
            user_data.pop("guided", None)
            user_data["guided_pending"] = False
        await update.message.reply_text("Draft dibatalkan.")

    async def _handle_version(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.message is None:
            return
        if not await self._authorize_message(update):
            return
        await update.message.reply_text(self._admin_info.version().to_user_message())

    async def _handle_diagnostics(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        del context
        if update.message is None:
            return
        if not await self._authorize_message(update):
            return
        await update.message.reply_text(self._admin_info.diagnostics().to_user_message())

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
        if update.message is None or update.effective_user is None:
            return
        if not await self._authorize_message(update):
            return

        user_data = _user_data(context)
        guided_state = user_data.get("guided") if user_data is not None else None
        if guided_state is not None:
            await self._handle_guided_field_answer(update, context, guided_state)
            return

        rate_limit = self._rate_limiter.check(str(update.effective_user.id))
        if not rate_limit.allowed:
            await update.message.reply_text(rate_limit.to_user_message())
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
        query = update.callback_query
        if query is None or update.effective_user is None or update.effective_chat is None:
            return

        await query.answer()
        identity = ChannelUserIdentity(
            channel="telegram",
            channel_user_id=str(update.effective_user.id),
        )

        user_data = _user_data(context)
        guided_pending = bool(user_data and user_data.get("guided_pending"))
        user_key = (
            f"telegram:{update.effective_user.id}"
            if guided_pending
            else str(update.effective_user.id)
        )
        if user_data is not None:
            user_data["guided_pending"] = False
            user_data.pop("guided", None)

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

    async def _handle_guided_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.message is None:
            return
        if not await self._authorize_message(update):
            return
        user_data = _user_data(context)
        if user_data is not None:
            user_data.pop("guided", None)
            user_data["guided_pending"] = False

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        intent.replace("_", " ").title(),
                        callback_data=f"guided:pick:{intent}",
                    )
                ]
                for intent in GUIDED_CAPTURE_INTENTS
            ]
        )
        await update.message.reply_text("Pilih jenis guided capture:", reply_markup=keyboard)

    async def _handle_guided_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if query is None or update.effective_user is None or update.effective_chat is None:
            return
        await query.answer()
        identity = ChannelUserIdentity(
            channel="telegram",
            channel_user_id=str(update.effective_user.id),
        )
        try:
            self._identity.require_authorized(identity)
        except UserAuthorizationError as exc:
            await query.edit_message_text(str(exc))
            return

        parts = (query.data or "").split(":")
        action = parts[1] if len(parts) > 1 else ""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        display_name = update.effective_user.full_name or None

        user_data = _user_data(context)

        if action == "cancel":
            if user_data is not None:
                user_data.pop("guided", None)
                user_data["guided_pending"] = False
            await query.edit_message_text("Guided capture dibatalkan.")
            return

        if action == "pick":
            intent = parts[2]
            if user_data is not None:
                user_data["guided"] = {"intent": intent, "field_idx": 0, "values": {}}
            await query.edit_message_text(
                f"Guided capture: {intent.replace('_', ' ').title()}"
            )
            await self._advance_guided_flow(
                chat_id=chat_id,
                user_id=user_id,
                display_name=display_name,
                context=context,
            )
            return

        state = user_data.get("guided") if user_data is not None else None
        if state is None:
            await query.edit_message_text(
                "Sesi guided capture sudah tidak aktif. Kirim /guided untuk mulai lagi."
            )
            return

        if action == "opt" and len(parts) == 4:
            state["values"][parts[2]] = parts[3]
            state["field_idx"] += 1
        elif action == "skip" and len(parts) == 3:
            state["field_idx"] += 1
        else:
            return

        if user_data is not None:
            user_data["guided"] = state
        await self._advance_guided_flow(
            chat_id=chat_id,
            user_id=user_id,
            display_name=display_name,
            context=context,
        )

    async def _handle_guided_field_answer(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        state: dict[str, Any],
    ) -> None:
        if update.message is None or update.effective_user is None or update.effective_chat is None:
            return

        fields = guided_capture_fields(state["intent"])
        field = fields[state["field_idx"]]
        raw = (update.message.text or "").strip()
        try:
            value = _coerce_guided_field_value(field, raw)
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return

        if value is not None:
            state["values"][field.key] = value
        state["field_idx"] += 1
        user_data = _user_data(context)
        if user_data is not None:
            user_data["guided"] = state

        await self._advance_guided_flow(
            chat_id=update.effective_chat.id,
            user_id=update.effective_user.id,
            display_name=update.effective_user.full_name or None,
            context=context,
        )

    async def _advance_guided_flow(
        self,
        *,
        chat_id: int,
        user_id: int,
        display_name: str | None,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        user_data = _user_data(context)
        state = user_data.get("guided") if user_data is not None else None
        if state is None:
            return

        fields = guided_capture_fields(state["intent"])
        if state["field_idx"] >= len(fields):
            await self._finish_guided_flow(
                chat_id=chat_id,
                user_id=user_id,
                display_name=display_name,
                context=context,
            )
            return

        field = fields[state["field_idx"]]
        if field.field_type == "priority":
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            option.title(),
                            callback_data=f"guided:opt:{field.key}:{option}",
                        )
                        for option in field.options
                    ]
                ]
            )
            await context.bot.send_message(
                chat_id=chat_id, text=f"Pilih {field.label}:", reply_markup=keyboard
            )
            return

        if field.required:
            await context.bot.send_message(chat_id=chat_id, text=f"{field.label}:")
            return

        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Lewati", callback_data=f"guided:skip:{field.key}")]]
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{field.label} (opsional, kirim '-' atau tekan Lewati):",
            reply_markup=keyboard,
        )

    async def _finish_guided_flow(
        self,
        *,
        chat_id: int,
        user_id: int,
        display_name: str | None,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        user_data = _user_data(context)
        state = user_data.pop("guided", None) if user_data is not None else None
        if state is None:
            return

        intent = state["intent"]
        values = state["values"]
        try:
            draft = GuidedCaptureDraft.model_validate(
                {
                    "intent": intent,
                    "payload": values,
                    "user_confirmation_text": _default_guided_confirmation_text(intent, values),
                    "original_text": f"guided:telegram:{intent}",
                }
            )
        except ValidationError as exc:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Input guided capture tidak valid: {exc}. Kirim /guided untuk mulai lagi.",
            )
            return

        message = ChannelMessage(
            channel="telegram",
            message_id=f"guided-{user_id}-{chat_id}",
            conversation_id=str(chat_id),
            user=ChannelUser(
                channel="telegram",
                channel_user_id=str(user_id),
                display_name=display_name,
            ),
            text=draft.original_text,
        )
        guided_flow = GuidedCaptureChannelFlow(
            capture_flow=self._capture_flow,
            channel=TelegramChannelAdapter(bot=context.bot),
        )
        result = await guided_flow.request_confirmation(message=message, draft=draft)
        if user_data is not None:
            user_data["guided_pending"] = result.status == "confirmation_required"

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


def _coerce_guided_field_value(field: GuidedCaptureField, raw: str) -> object | None:
    if not raw or raw.lower() in {"-", "skip"}:
        if field.required:
            raise ValueError(f"{field.label} wajib diisi. Kirim nilainya.")
        return None

    if field.field_type == "date":
        try:
            return date.fromisoformat(raw)
        except ValueError:
            raise ValueError("Format tanggal harus YYYY-MM-DD. Coba lagi.") from None

    if field.field_type == "duration_minutes":
        try:
            return int(raw)
        except ValueError:
            raise ValueError("Durasi harus berupa angka menit. Coba lagi.") from None

    if field.field_type == "priority":
        normalized = raw.lower()
        if normalized not in field.options:
            options = ", ".join(field.options)
            raise ValueError(f"Pilih salah satu: {options}.")
        return normalized

    return raw


def _default_guided_confirmation_text(intent: str, values: dict[str, object]) -> str:
    title = values.get("title")
    if not isinstance(title, str) or not title.strip():
        return f"Konfirmasi guided capture {intent}?"
    return f'Konfirmasi {intent} "{title}"?'
