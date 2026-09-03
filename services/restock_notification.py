import logging
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import AllCategoriesCallback
from enums.bot_entity import BotEntity
from enums.language import Language
from repositories.restock_subscription import RestockSubscriptionRepository
from utils.utils import get_text

logger = logging.getLogger(__name__)


class RestockNotificationService:

    @staticmethod
    def is_batstore_out_of_stock(product) -> bool:
        """Returns True if product has 0 stock or is a stock-type product with no stock."""
        if product is None:
            return True
        delivery = getattr(product, "delivery_type", None) or "stock"
        stock = getattr(product, "stock", None)
        if delivery == "stock":
            return not (stock is not None and stock > 0)
        return stock is not None and stock <= 0

    @staticmethod
    async def auto_subscribe_if_out_of_stock(
        telegram_id: int,
        user_id: int | None,
        product,
        language: Language,
        session: AsyncSession | Session
    ) -> bool:
        """If product is out of stock, automatically subscribe user for restock alerts.
        Returns True if subscribed (was out of stock), False otherwise.
        """
        if not RestockNotificationService.is_batstore_out_of_stock(product):
            return False
        lang_str = language.value if hasattr(language, "value") else str(language)
        await RestockSubscriptionRepository.subscribe(
            telegram_id=telegram_id,
            user_id=user_id,
            batstore_product_id=product.product_id,
            subcategory_id=None,
            language=lang_str,
            session=session
        )
        return True

    @staticmethod
    async def is_subscribed(
        telegram_id: int,
        product_id: int,
        session: AsyncSession | Session
    ) -> bool:
        return await RestockSubscriptionRepository.is_subscribed(
            telegram_id=telegram_id,
            batstore_product_id=product_id,
            subcategory_id=None,
            session=session
        )

    @staticmethod
    async def toggle_batstore_subscription(
        telegram_id: int,
        user_id: int | None,
        product_id: int,
        language: Language,
        session: AsyncSession | Session
    ) -> bool:
        """Toggle subscription for a BatStore product. Returns True if now subscribed, False if unsubscribed."""
        is_sub = await RestockSubscriptionRepository.is_subscribed(
            telegram_id=telegram_id,
            batstore_product_id=product_id,
            subcategory_id=None,
            session=session
        )
        if is_sub:
            await RestockSubscriptionRepository.unsubscribe(
                telegram_id=telegram_id,
                batstore_product_id=product_id,
                subcategory_id=None,
                session=session
            )
            return False
        else:
            lang_str = language.value if hasattr(language, "value") else str(language)
            await RestockSubscriptionRepository.subscribe(
                telegram_id=telegram_id,
                user_id=user_id,
                batstore_product_id=product_id,
                subcategory_id=None,
                language=lang_str,
                session=session
            )
            return True

    @staticmethod
    async def notify_batstore_product_restocked(
        batstore_product_id: int,
        product_name: str,
        session: AsyncSession | Session,
        bot: Bot | None = None
    ) -> int:
        """Notify all pending subscribers that a BatStore product is back in stock."""
        subscribers = await RestockSubscriptionRepository.get_active_subscribers_for_product(
            batstore_product_id, session
        )
        if not subscribers:
            return 0

        if bot is None:
            try:
                from bot import bot as default_bot
                bot = default_bot
            except Exception as e:
                logger.error("Could not import bot for restock notification: %s", e)
                return 0

        notified_ids = []
        for sub in subscribers:
            try:
                lang = Language(sub.language) if sub.language in [l.value for l in Language] else Language.EN
            except Exception:
                lang = Language.EN

            notice_text = get_text(lang, BotEntity.USER, "restock_notification_msg").format(
                product_name=product_name
            )

            # Add inline button to view product directly
            kb = InlineKeyboardBuilder()
            view_btn_text = get_text(lang, BotEntity.USER, "restock_view_product_btn")
            kb.button(
                text=view_btn_text,
                callback_data=AllCategoriesCallback.create(
                    level=2,
                    batstore_product_id=batstore_product_id
                ).pack()
            )
            try:
                await bot.send_message(
                    chat_id=sub.telegram_id,
                    text=notice_text,
                    parse_mode="HTML",
                    reply_markup=kb.as_markup()
                )
                notified_ids.append(sub.id)
            except Exception as e:
                logger.warning("Failed to send restock notification to tg %s: %s", sub.telegram_id, e)
                notified_ids.append(sub.id)

        if notified_ids:
            await RestockSubscriptionRepository.mark_notified(notified_ids, session)
        return len(notified_ids)

    @staticmethod
    async def notify_subcategory_restocked(
        subcategory_id: int,
        subcategory_name: str,
        session: AsyncSession | Session,
        bot: Bot | None = None
    ) -> int:
        """Notify all pending subscribers that a native subcategory is back in stock."""
        subscribers = await RestockSubscriptionRepository.get_active_subscribers_for_subcategory(
            subcategory_id, session
        )
        if not subscribers:
            return 0

        if bot is None:
            try:
                from bot import bot as default_bot
                bot = default_bot
            except Exception as e:
                logger.error("Could not import bot for restock notification: %s", e)
                return 0

        notified_ids = []
        for sub in subscribers:
            try:
                lang = Language(sub.language) if sub.language in [l.value for l in Language] else Language.EN
            except Exception:
                lang = Language.EN

            notice_text = get_text(lang, BotEntity.USER, "restock_notification_msg").format(
                product_name=subcategory_name
            )
            kb = InlineKeyboardBuilder()
            view_btn_text = get_text(lang, BotEntity.USER, "restock_view_product_btn")
            kb.button(
                text=view_btn_text,
                callback_data=AllCategoriesCallback.create(
                    level=2,
                    subcategory_id=subcategory_id
                ).pack()
            )
            try:
                await bot.send_message(
                    chat_id=sub.telegram_id,
                    text=notice_text,
                    parse_mode="HTML",
                    reply_markup=kb.as_markup()
                )
                notified_ids.append(sub.id)
            except Exception as e:
                logger.warning("Failed to send subcategory restock notification to tg %s: %s", sub.telegram_id, e)
                notified_ids.append(sub.id)

        if notified_ids:
            await RestockSubscriptionRepository.mark_notified(notified_ids, session)
        return len(notified_ids)
