import json
import logging
from aiogram.types import Message
from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_commit, session_execute
from models.batstore_product import BatStoreProduct, _PRODUCT_ICON_MAP, format_product_icon
from repositories.batstore_product import BatStoreProductRepository
from services.config import ConfigService

CONFIG_KEY = "CUSTOM_EMOJI_RULES"


class CustomEmojiService:

    @staticmethod
    async def get_rules(session: AsyncSession | Session) -> dict[str, dict[str, str | None]]:
        """Return dict of {keyword: {'emoji': str, 'custom_emoji_id': str | None}}.

        Merges built-in defaults with admin database overrides.
        """
        rules: dict[str, dict[str, str | None]] = {}
        # 1. Base defaults
        for kw, fallback_emoji, custom_id in _PRODUCT_ICON_MAP:
            rules[kw.lower()] = {
                "emoji": fallback_emoji,
                "custom_emoji_id": custom_id,
            }

        # 2. Database overrides
        try:
            raw = await ConfigService.get(session, CONFIG_KEY)
            if raw:
                custom_rules = json.loads(raw)
                if isinstance(custom_rules, dict):
                    for k, v in custom_rules.items():
                        if isinstance(v, dict):
                            rules[k.lower()] = {
                                "emoji": v.get("emoji") or "⚡",
                                "custom_emoji_id": v.get("custom_emoji_id"),
                            }
        except Exception as e:
            logging.warning("Failed to load CUSTOM_EMOJI_RULES: %s", e)

        return rules

    @staticmethod
    async def set_rule(keyword: str, emoji: str, custom_emoji_id: str | None,
                       session: AsyncSession | Session) -> int:
        """Set an animated custom emoji rule for a keyword and bulk-update matching products.

        Returns the number of products updated.
        """
        kw = keyword.strip().lower()
        if not kw:
            return 0

        # 1. Update AppConfig
        rules = await CustomEmojiService.get_rules(session)
        rules[kw] = {
            "emoji": emoji,
            "custom_emoji_id": custom_emoji_id,
        }
        await ConfigService.set(session, CONFIG_KEY, json.dumps(rules))

        # 2. Bulk-update matching products in batstore_products
        pattern = f"%{kw}%"
        stmt = (
            update(BatStoreProduct)
            .where(BatStoreProduct.name.ilike(pattern))
            .values(emoji=emoji, custom_emoji_id=custom_emoji_id)
        )
        res = await session_execute(stmt, session)
        await BatStoreProductRepository.invalidate_cache()
        await session_commit(session)

        count = getattr(res, "rowcount", 0) or 0
        return count

    @staticmethod
    def detect_icon(name: str, rules: dict[str, dict[str, str | None]]) -> tuple[str, str | None]:
        """Match product name against rules dictionary."""
        lower = name.lower()
        for kw, rule in rules.items():
            if kw in lower:
                return rule.get("emoji") or "⚡", rule.get("custom_emoji_id")
        return "⚡", None

    @staticmethod
    def extract_from_message(message: Message) -> tuple[str, str | None] | None:
        """Extract custom_emoji_id and character from a message with custom emoji."""
        text = message.text or message.caption or ""
        if message.entities:
            for entity in message.entities:
                if entity.type == "custom_emoji" and entity.custom_emoji_id:
                    char = text[entity.offset:entity.offset + entity.length] if text else "✨"
                    return char or "✨", str(entity.custom_emoji_id)

        # Fallback: if user sent a standard emoji without custom_emoji_id
        cleaned = text.strip()
        if cleaned and len(cleaned) <= 4:
            return cleaned, None
        return None
