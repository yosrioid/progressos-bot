from dataclasses import dataclass
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from progressos_bot.channels.base import ConfirmationRequest

TELEGRAM_CHANNEL = "telegram"


@dataclass
class TelegramChannelAdapter:
    bot: Any

    async def send_text(self, *, conversation_id: str, text: str) -> None:
        await self.bot.send_message(chat_id=int(conversation_id), text=text)

    async def request_confirmation(self, request: ConfirmationRequest) -> None:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Confirm", callback_data="confirm"),
                    InlineKeyboardButton("Cancel", callback_data="cancel"),
                ]
            ]
        )
        await self.bot.send_message(
            chat_id=int(request.conversation_id),
            text=request.prompt_text,
            reply_markup=keyboard,
        )
