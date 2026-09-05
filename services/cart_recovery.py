import asyncio
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from aiogram.utils.keyboard import InlineKeyboardBuilder
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

    @classmethod
    def get_redis(cls):
        if cls._redis is None:
            try:
                from bot import redis
                cls._redis = redis
            except Exception:
                pass
        return cls._redis

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
            r = CartRecoveryService.get_redis()
            if r is not None:
                try:
                    exists = await r.get(key)
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

        # Also check Redis TMA abandoned carts
        r = CartRecoveryService.get_redis()
        if r is not None:
            try:
                import time
                import json
                from aiogram.types import InlineKeyboardButton
                now_ts = time.time()
                tma_keys = []
                async for k in r.scan_iter("ghstore:tma_cart:*"):
                    tma_keys.append(k)

                from repositories.user import UserRepository
                for raw_k in tma_keys:
                    k_str = raw_k.decode() if isinstance(raw_k, bytes) else str(raw_k)
                    val_raw = await r.get(raw_k)
                    if not val_raw:
                        continue
                    try:
                        cart_obj = json.loads(val_raw)
                        tg_id = int(cart_obj.get("tg_id") or 0)
                        updated_at = float(cart_obj.get("updated_at") or 0.0)
                        items = cart_obj.get("items") or []
                        if not tg_id or not items or (now_ts - updated_at) < 7200:  # wait at least 2 hours
                            continue

                        nudge_key = f"ghstore:cart_nudge:tma:{tg_id}"
                        if await r.get(nudge_key):
                            continue

                        user_row = await UserRepository.get_by_tgid(tg_id, session)
                        if not user_row or not user_row.can_receive_messages or user_row.is_banned:
                            continue

                        item_names = ", ".join(it.get("name") or "Product" for it in items[:3])
                        bot_user = getattr(config, "BOT_USERNAME", None) or "GHStoreBot"
                        tma_url = f"https://t.me/{bot_user}/app"
                        kb_tma = InlineKeyboardBuilder()
                        kb_tma.row(InlineKeyboardButton(text="🛍️ إكمال طلب السلة في المتجر", url=tma_url))

                        msg = (
                            "🛒 <b>سلة مشترياتك في انتظارك!</b>\n\n"
                            f"لديك <b>{len(items)} منتج</b> في سلة التسوق ({item_names}).\n"
                            "يمكنك إتمام الطلب مباشرة وبضغطة واحدة من داخل المتجر:"
                        )
                        await NotificationService.send_to_user(msg, tg_id, kb_tma.as_markup())
                        await r.setex(nudge_key, 86400, "1")
                        nudged += 1
                    except Exception as ex:
                        logging.warning("Error processing TMA cart recovery for %s: %s", raw_k, ex)
            except Exception as e:
                logging.warning("Failed to scan TMA abandoned carts in Redis: %s", e)

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
