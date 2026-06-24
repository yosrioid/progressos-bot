from dataclasses import dataclass, field
from typing import Any

import pytest

from progressos_bot.bot import ProgressOSTelegramBot
from progressos_bot.core.admin import AdminInfoService, ConfigurationDiagnostics, VersionInfo
from progressos_bot.core.capture_flow import CaptureFlow
from progressos_bot.identity import TelegramAllowlist, TelegramProgressOSUserMap
from progressos_bot.pending import InMemoryPendingActionStore
from progressos_bot.schemas import ProgressOSActionRequest, ProgressOSActionResponse


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    async def send_message(
        self, *, chat_id: int, text: str, reply_markup: Any = None
    ) -> None:
        self.sent_messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


class FakeContext:
    def __init__(self, bot: FakeBot | None = None) -> None:
        self.user_data: dict[str, Any] = {}
        self.bot = bot or FakeBot()
        self.args: list[str] = []


class FakeChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class FakeUser:
    def __init__(self, user_id: int, full_name: str = "Test User") -> None:
        self.id = user_id
        self.full_name = full_name


class FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text: str, reply_markup: Any = None) -> None:
        self.replies.append(text)


class FakeCallbackQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.answered = False
        self.edits: list[str] = []

    async def answer(self) -> None:
        self.answered = True

    async def edit_message_text(self, text: str, reply_markup: Any = None) -> None:
        self.edits.append(text)


class FakeUpdate:
    def __init__(
        self,
        *,
        user_id: int,
        chat_id: int = 555,
        message: FakeMessage | None = None,
        callback_query: FakeCallbackQuery | None = None,
        full_name: str = "Test User",
    ) -> None:
        self.effective_user = FakeUser(user_id, full_name=full_name)
        self.effective_chat = FakeChat(chat_id)
        self.message = message
        self.callback_query = callback_query


@dataclass
class FakeProgressOS:
    submitted_requests: list[ProgressOSActionRequest] = field(default_factory=list)

    async def submit_action(self, request: ProgressOSActionRequest) -> ProgressOSActionResponse:
        self.submitted_requests.append(request)
        return ProgressOSActionResponse(message="Capture tersimpan.")


def make_bot(
    *,
    allowed: str = "123",
    mappings: str = "123:77",
    progressos: FakeProgressOS | None = None,
) -> tuple[ProgressOSTelegramBot, FakeProgressOS]:
    progressos = progressos or FakeProgressOS()
    capture_flow = CaptureFlow(
        parser=object(),  # type: ignore[arg-type]
        progressos=progressos,
        pending=InMemoryPendingActionStore(ttl_seconds=60),
        correlation_id_factory=lambda: "corr-guided",
    )
    bot = ProgressOSTelegramBot(
        token="token",
        parser=None,
        progressos=progressos,  # type: ignore[arg-type]
        authorizer=TelegramAllowlist.from_csv(allowed),
        user_map=TelegramProgressOSUserMap.from_csv(mappings),
        admin_info=AdminInfoService(
            version_info=VersionInfo(
                app_name="progressos-bot",
                app_version="0.1.0",
                app_env="local",
                run_mode="polling",
                log_format="text",
            ),
            diagnostics=ConfigurationDiagnostics(
                app_env="local",
                run_mode="polling",
                log_format="text",
                capture_enabled_intents={"create_task", "create_blocker"},
                capture_pre_parser_guard_mode="off",
                pending_store_enabled=False,
                retry_queue_enabled=False,
                allowlist_configured=bool(allowed),
                user_map_configured=bool(mappings),
                webhook_secret_configured=False,
            ),
        ),
        capture_flow=capture_flow,
    )
    return bot, progressos


@pytest.mark.asyncio
async def test_handle_guided_start_sends_intent_keyboard() -> None:
    bot, _ = make_bot()
    update = FakeUpdate(user_id=123, message=FakeMessage())
    context = FakeContext()

    await bot._handle_guided_start(update, context)

    assert update.message.replies == ["Pilih jenis guided capture:"]
    assert context.user_data["guided_pending"] is False


@pytest.mark.asyncio
async def test_guided_callback_rejects_unauthorized_user() -> None:
    bot, _ = make_bot(allowed="123")
    update = FakeUpdate(user_id=999, callback_query=FakeCallbackQuery("guided:pick:create_task"))
    context = FakeContext()

    await bot._handle_guided_callback(update, context)

    assert update.callback_query.edits == ["User belum diizinkan memakai bot ini."]
    assert "guided" not in context.user_data


@pytest.mark.asyncio
async def test_guided_pick_intent_prompts_first_required_field() -> None:
    bot, _ = make_bot()
    update = FakeUpdate(
        user_id=123, callback_query=FakeCallbackQuery("guided:pick:create_blocker")
    )
    context = FakeContext()

    await bot._handle_guided_callback(update, context)

    assert context.user_data["guided"]["intent"] == "create_blocker"
    assert context.user_data["guided"]["field_idx"] == 0
    assert context.bot.sent_messages[-1]["text"] == "Title:"


@pytest.mark.asyncio
async def test_guided_text_answer_advances_and_skip_button_skips_optional_field() -> None:
    bot, _ = make_bot()
    context = FakeContext()
    pick_update = FakeUpdate(
        user_id=123, callback_query=FakeCallbackQuery("guided:pick:create_blocker")
    )
    await bot._handle_guided_callback(pick_update, context)

    title_update = FakeUpdate(user_id=123, message=FakeMessage(text="Server down"))
    await bot._handle_message(title_update, context)

    assert context.user_data["guided"]["values"]["title"] == "Server down"
    assert "opsional" in context.bot.sent_messages[-1]["text"]

    skip_update = FakeUpdate(
        user_id=123, callback_query=FakeCallbackQuery("guided:skip:description")
    )
    await bot._handle_guided_callback(skip_update, context)

    assert "description" not in context.user_data["guided"]["values"]
    assert context.bot.sent_messages[-1]["text"] == "Pilih Severity:"


@pytest.mark.asyncio
async def test_guided_field_answer_rejects_invalid_value_and_keeps_field_idx() -> None:
    bot, _ = make_bot()
    context = FakeContext()
    pick_update = FakeUpdate(
        user_id=123, callback_query=FakeCallbackQuery("guided:pick:create_blocker")
    )
    await bot._handle_guided_callback(pick_update, context)

    empty_title_update = FakeUpdate(user_id=123, message=FakeMessage(text=""))
    await bot._handle_message(empty_title_update, context)

    assert empty_title_update.message.replies == ["Title wajib diisi. Kirim nilainya."]
    assert context.user_data["guided"]["field_idx"] == 0


@pytest.mark.asyncio
async def test_guided_priority_option_completes_flow_and_requests_confirmation() -> None:
    bot, progressos = make_bot()
    context = FakeContext()
    pick_update = FakeUpdate(
        user_id=123, callback_query=FakeCallbackQuery("guided:pick:create_blocker")
    )
    await bot._handle_guided_callback(pick_update, context)
    await bot._handle_message(
        FakeUpdate(user_id=123, message=FakeMessage(text="Server down")), context
    )
    await bot._handle_guided_callback(
        FakeUpdate(user_id=123, callback_query=FakeCallbackQuery("guided:skip:description")),
        context,
    )
    await bot._handle_guided_callback(
        FakeUpdate(
            user_id=123,
            callback_query=FakeCallbackQuery("guided:opt:severity:high"),
        ),
        context,
    )

    assert "guided" not in context.user_data
    assert context.user_data["guided_pending"] is True
    last_message = context.bot.sent_messages[-1]
    assert last_message["reply_markup"] is not None
    assert progressos.submitted_requests == []


@pytest.mark.asyncio
async def test_guided_confirmation_uses_prefixed_user_key_and_submits() -> None:
    bot, progressos = make_bot()
    context = FakeContext()
    await bot._handle_guided_callback(
        FakeUpdate(user_id=123, callback_query=FakeCallbackQuery("guided:pick:create_blocker")),
        context,
    )
    await bot._handle_message(
        FakeUpdate(user_id=123, message=FakeMessage(text="Server down")), context
    )
    await bot._handle_guided_callback(
        FakeUpdate(user_id=123, callback_query=FakeCallbackQuery("guided:skip:description")),
        context,
    )
    await bot._handle_guided_callback(
        FakeUpdate(user_id=123, callback_query=FakeCallbackQuery("guided:opt:severity:high")),
        context,
    )

    confirm_query = FakeCallbackQuery("confirm")
    await bot._handle_confirmation(
        FakeUpdate(user_id=123, callback_query=confirm_query), context
    )

    assert confirm_query.edits == ["ProgressOS: Capture tersimpan."]
    assert len(progressos.submitted_requests) == 1
    assert progressos.submitted_requests[0].parsed_action.intent == "create_blocker"
    assert progressos.submitted_requests[0].parsed_action.payload.severity == "high"
    assert context.user_data["guided_pending"] is False


@pytest.mark.asyncio
async def test_guided_callback_cancel_clears_session() -> None:
    bot, _ = make_bot()
    context = FakeContext()
    await bot._handle_guided_callback(
        FakeUpdate(user_id=123, callback_query=FakeCallbackQuery("guided:pick:create_task")),
        context,
    )

    cancel_query = FakeCallbackQuery("guided:cancel")
    await bot._handle_guided_callback(FakeUpdate(user_id=123, callback_query=cancel_query), context)

    assert cancel_query.edits == ["Guided capture dibatalkan."]
    assert "guided" not in context.user_data
    assert context.user_data["guided_pending"] is False


@pytest.mark.asyncio
async def test_handle_cancel_clears_guided_session_and_both_pending_drafts() -> None:
    bot, _ = make_bot()
    context = FakeContext()
    await bot._handle_guided_callback(
        FakeUpdate(user_id=123, callback_query=FakeCallbackQuery("guided:pick:create_task")),
        context,
    )

    cancel_update = FakeUpdate(user_id=123, message=FakeMessage())
    await bot._handle_cancel(cancel_update, context)

    assert cancel_update.message.replies == ["Draft dibatalkan."]
    assert "guided" not in context.user_data
    assert context.user_data["guided_pending"] is False
