from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

import config


def create_telegram_session() -> AiohttpSession:
    if config.TELEGRAM_PROXY_URL:
        return AiohttpSession(proxy=config.TELEGRAM_PROXY_URL)
    return AiohttpSession()


def create_bot(token: str, session: AiohttpSession | None = None) -> Bot:
    session = session or create_telegram_session()
    return Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )


from typing import Any
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAnimation,
)


async def safe_edit_message(
    callback: CallbackQuery,
    content: Any,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Safely edit a message regardless of whether current message is text, caption, or media.

    Handles TelegramBadRequest gracefully:
    - If content is media and current is text -> deletes old and answers with photo
    - If content is text and current is media -> edits caption, or deletes and answers with text
    - Always answers callback query to prevent Telegram loading spinner from hanging
    """
    try:
        await callback.answer()
    except Exception:
        pass

    if isinstance(content, (InputMediaPhoto, InputMediaVideo, InputMediaAnimation)):
        try:
            await callback.message.edit_media(media=content, reply_markup=reply_markup)
            return
        except Exception as e:
            if "message is not modified" in str(e).lower():
                return
        try:
            await callback.message.delete()
        except Exception:
            pass
        from utils.utils import get_bot_photo_id
        photo = getattr(content, "media", None) or get_bot_photo_id()
        caption = getattr(content, "caption", None)
        await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
        return
    else:
        text = str(content)
        # Try editing text
        try:
            await callback.message.edit_text(text=text, reply_markup=reply_markup)
            return
        except Exception as e:
            if "message is not modified" in str(e).lower():
                return
        # Try editing caption if current message has media
        try:
            await callback.message.edit_caption(caption=text, reply_markup=reply_markup)
            return
        except Exception as e:
            if "message is not modified" in str(e).lower():
                return
        # If both failed, delete and send fresh message
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text=text, reply_markup=reply_markup)


import re

def clean_tg_emojis(raw: str | None) -> str:
    """Strip Telegram <tg-emoji> markup and placeholder leaks, preserving native UTF-8 emojis."""
    if not raw:
        return ""
    text = str(raw)
    # 1. Extract unicode emoji from <tg-emoji emoji-id="...">📱</tg-emoji>
    text = re.sub(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", r"\1", text, flags=re.DOTALL)
    # 2. Strip any placeholder leaks like TG_EMOJI_0, __TG_EMOJI_1__, TGemoji1, etc.
    text = re.sub(r"_*TG_?EMOJI_\d+_*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bTG_?emoji\d+\b", "", text, flags=re.IGNORECASE)
    return text.strip()
