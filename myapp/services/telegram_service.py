import logging
import telegram
from pydantic import BaseModel
from typing import Optional, Any, List, Dict
import os
from typing import List, Dict, Any, Optional
from telegram import Bot, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)


class MessageRequest(BaseModel):
    to: str
    text: Optional[str] = None
    template: Optional[str] = None
    language: Optional[str] = "en_US"
    components: Optional[List[Dict[str, Any]]] = None  # For template variables

class TelegramSendMessageService:

    def __init__(self):
        self._bot = None

    def _get_bot(self):
        if self._bot is None:
            token = os.getenv("TELEGRAM_TOKEN")
            if not token:
                raise RuntimeError("TELEGRAM_TOKEN is not set!")
            self._bot = Bot(token=token)  # create bot
        return self._bot

    
    def _build_reply_markup(self, components: Optional[List[Dict[str, Any]]]):
        """
        Returns either a ReplyKeyboardMarkup or InlineKeyboardMarkup object
        based on the first matching component found.
        
        Rules:
        - If multiple components exist, the FIRST one determines the markup type.
        - ReplyKeyboardMarkup expects "buttons" as list of lists of strings.
        - InlineKeyboardMarkup expects "buttons" as list of lists of dicts {text, url?, callback_data?}.
        """
        if not components:
            return None

        for component in components:
            ctype = component.get("ctype")
            buttons = component.get("buttons", [])

            if ctype == "reply_keyboard":
                return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

            elif ctype == "inline_keyboard":
                inline_buttons = [
                    [InlineKeyboardButton(text=btn["text"], url=btn.get("url"), callback_data=btn.get("callback_data")) for btn in row]
                    for row in buttons
                ]
                return InlineKeyboardMarkup(inline_buttons)

        return None
    
    async def send_telegram_message(self, message_req: MessageRequest):
        try:
            bot = self._get_bot()   # make sure bot is created
            chat_id = message_req.to
            text = message_req.text
            reply_markup = self._build_reply_markup(message_req.components)
            print(f"markup {reply_markup}")
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)


        except Exception as error:
            logger.exception("Failed to send a message: %s", error)
            return None