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
        caption = getattr(content, "caption", None)
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

        photo = getattr(content, "media", None)
        if photo and photo != "no_image_placeholder" and not str(photo).startswith("0AgAC"):
            try:
                await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
                return
            except Exception:
                pass

        if caption:
            await callback.message.answer(text=caption, reply_markup=reply_markup)
            return
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


import functools
import re

_TG_EMOJI_TAG_RE = re.compile(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", flags=re.DOTALL)
_TG_EMOJI_PLACEHOLDER_RE = re.compile(r"_*TG_?EMOJI_\d+_*", flags=re.IGNORECASE)
_TG_EMOJI_WORD_RE = re.compile(r"\bTG_?emoji\d+\b", flags=re.IGNORECASE)


@functools.lru_cache(maxsize=2048)
def clean_tg_emojis(raw: str | None) -> str:
    """Strip Telegram <tg-emoji> markup and placeholder leaks, preserving native UTF-8 emojis."""
    if not raw:
        return ""
    text = _TG_EMOJI_TAG_RE.sub(r"\1", str(raw))
    text = _TG_EMOJI_PLACEHOLDER_RE.sub("", text)
    text = _TG_EMOJI_WORD_RE.sub("", text)
    return text.strip()

import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any

def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict[str, Any]:
    """Cryptographically validate Telegram WebApp initData string using HMAC-SHA256."""
    if not init_data:
        raise ValueError("Missing init_data")
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    parsed.pop("signature", None)
    if not received_hash:
        raise ValueError("Missing hash parameter")
    auth_date = int(parsed.get("auth_date", 0))
    if max_age_seconds > 0 and (time.time() - auth_date) > max_age_seconds:
        raise ValueError("init_data has expired")
    check_items = [f"{k}={v}" for k, v in sorted(parsed.items())]
    data_check_string = "\n".join(check_items)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Invalid init_data signature")
    result = dict(parsed)
    if "user" in result:
        try:
            result["user"] = json.loads(result["user"])
        except Exception:
            pass
    return result
