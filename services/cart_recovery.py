import asyncio
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import CartCallback
from db import get_db_session, session_execute
from models.cart import Cart
from models.cartItem import CartItem
from models.user import User
from services.notification import NotificationService


class CartRecoveryService:

    _redis = None

    @classmethod
    def set_redis(cls, r) -> None:
        cls._redis = r

    @staticmethod
    async def run_recovery_check(session: AsyncSession | Session) -> int:
        """Find users with items in cart and send a friendly nudge."""
        # Find distinct user_ids with items in cart
        stmt = (
            select(User)
            .join(Cart, Cart.user_id == User.id)
            .join(CartItem, CartItem.cart_id == Cart.id)
            .where(User.can_receive_messages == True, User.is_banned == False)
            .distinct()
        )
        res = await session_execute(stmt, session)
        users = list(res.scalars().all())

        nudged = 0
        sym = config.CURRENCY.get_localized_symbol()
        for u in users:
            key = f"ghstore:cart_nudge:{u.id}"
            if CartRecoveryService._redis is not None:
                try:
                    exists = await CartRecoveryService._redis.get(key)
                    if exists:
                        continue
                except Exception:
                    pass

            balance = round((u.top_up_amount or 0) - (u.consume_records or 0), 2)
            caption = (
                "🛒 <b>You left items in your shopping cart!</b>\n\n"
                f"Your balance: <b>{balance:.2f}{sym}</b>\n\n"
                "Tap below to review your cart and complete your order with one tap:"
            )
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            kb = InlineKeyboardBuilder()
            kb.button(text="🛒 Open Cart & Checkout", callback_data=CartCallback.create(level=0).pack())

            try:
                await NotificationService.send_to_user(caption, u.telegram_id, kb.as_markup())
                nudged += 1
                if CartRecoveryService._redis is not None:
                    try:
                        await CartRecoveryService._redis.setex(key, 86400, "1")  # at most 1 nudge per 24h
                    except Exception:
                        pass
            except Exception as e:
                logging.debug("Could not send cart nudge to %s: %s", u.telegram_id, e)

        return nudged


async def cart_recovery_cron():
    """Background task checking abandoned carts every 3 hours."""
    while True:
        await asyncio.sleep(10800)  # every 3 hours
        try:
            async with get_db_session() as session:
                count = await CartRecoveryService.run_recovery_check(session)
            if count > 0:
                logging.info("Sent cart abandonment nudges to %s users", count)
        except Exception as e:
            logging.warning("Cart recovery check failed: %s", e)
