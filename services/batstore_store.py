import logging
import hashlib
from html import escape

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, WebAppInfo
from fastapi import HTTPException
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from enums.bot_entity import BotEntity
from callbacks import BatStoreCallback, RestockCallback
from db import session_commit
from services.restock_notification import RestockNotificationService
from enums.language import Language
from models.batstore_product import BatStoreProduct, format_product_icon
from repositories.batstore_product import BatStoreProductRepository
from repositories.user import UserRepository
from services.batstore import BatStoreService
from services.notification import NotificationService
from utils.utils import get_text
from utils.telegram import clean_tg_emojis

CART_KEY = "batstore_cart"
PAGE_SIZE = 8


class BatStoreStoreService:

    @staticmethod
    def _requires_mini_app(product) -> bool:
        meta = getattr(product, "extra_meta", None) or {}
        return bool(meta.get("items") or meta.get("required_fields") or
                    product.delivery_type in ("direct_topup", "game_recharge", "activation"))

    @staticmethod
    def _mini_app_checkout(product, language):
        kb = InlineKeyboardBuilder()
        host = (getattr(config, "TMA_HOST", None) or config.WEBHOOK_HOST).rstrip("/")
        kb.button(text="فتح المتجر · Open store", web_app=WebAppInfo(url=f"{host}/app?startapp=prod_{product.product_id}"))
        kb.row(BatStoreCallback.create(level=0).get_back_button(language, 0))
        return "اختر الخيارات وأدخل البيانات المطلوبة في المتجر.\nChoose your options and enter the required details in the store.", kb

    @staticmethod
    async def _quoted_total(product, user, qty, session):
        from services.checkout import priced_product
        from services.sale_pricing import price_lines
        from services.user import get_vip_tier_info
        _, cost, price = await priced_product(product, {}, user, session)
        _, discount = get_vip_tier_info(getattr(user, "consume_records", 0), getattr(user, "custom_discount_pct", None))
        (total,), _ = price_lines([(price, cost, qty, BatStoreService.get_volume_discount(qty))], discount_pct=discount)
        return float(total)

    # ------------------------------------------------------------- navigation

    @staticmethod
    async def catalog(telegram_id: int,
                      callback_data: BatStoreCallback,
                      session: AsyncSession | Session,
                      language: Language) -> tuple[str, InlineKeyboardBuilder]:
        products = await BatStoreProductRepository.get_visible(session)
        products = [p for p in products if not p.hidden]
        page = callback_data.page or 0
        total_pages = max(1, (len(products) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, total_pages - 1)
        start = page * PAGE_SIZE
        slice_ = products[start:start + PAGE_SIZE]

        kb_builder = InlineKeyboardBuilder()
        sym = config.CURRENCY.get_localized_symbol()
        for p in slice_:
            icon = getattr(p, "emoji", None) or "⚡"
            label = f"{icon} {p.name}"
            if p.sell_price_usd is not None:
                label = f"{label} — {p.sell_price_usd:.2f}{sym}"
            is_oos = RestockNotificationService.is_batstore_out_of_stock(p)
            if is_oos:
                label = f"🔴 {label}{get_text(language, BotEntity.USER, 'batstore_out_of_stock')}"
            elif p.delivery_type != "stock" and not (p.stock and p.stock > 0):
                label += f" ({p.stock if p.stock is not None else 0} left)"
            kb_builder.button(
                text=label,
                callback_data=BatStoreCallback.create(level=1, product_id=p.product_id).pack()
            )
        kb_builder.adjust(1)

        if total_pages > 1:
            row = []
            if page > 0:
                row.append(kb_builder.button(
                    text=get_text(language, BotEntity.COMMON, "pagination_previous"),
                    callback_data=BatStoreCallback.create(level=0, page=page - 1).pack()
                ))
            row.append(kb_builder.button(
                text=f"• {page + 1}/{total_pages} •",
                callback_data=BatStoreCallback.create(level=0, page=page).pack()
            ))
            if page < total_pages - 1:
                row.append(kb_builder.button(
                    text=get_text(language, BotEntity.COMMON, "pagination_next"),
                    callback_data=BatStoreCallback.create(level=0, page=page + 1).pack()
                ))
            kb_builder.row(*row)

        kb_builder.row(BatStoreCallback.create(level=0).get_back_button(language, 0))

        if not products:
            caption = get_text(language, BotEntity.USER, "batstore_empty")
        else:
            caption = get_text(language, BotEntity.USER, "batstore_title")
        return caption, kb_builder

    @staticmethod
    def _effective_price(product, user) -> float:
        if user and getattr(user, "is_reseller", False):
            from services.sale_pricing import compute_reseller_price
            return compute_reseller_price(
                cost=product.cost_usd,
                retail_price=product.sell_price_usd,
                reseller_price_usd=getattr(product, "reseller_price_usd", None),
                reseller_margin_pct=getattr(product, "reseller_margin_pct", None),
            )
        return float(product.sell_price_usd or 0.0)

    async def detail(callback: CallbackQuery,
                     callback_data: BatStoreCallback,
                     state: FSMContext,
                     session: AsyncSession | Session,
                     language: Language) -> tuple[str, InlineKeyboardBuilder]:
        product = await BatStoreProductRepository.get_by_product_id(callback_data.product_id, session)
        if product is None or product.hidden:
            kb_builder = InlineKeyboardBuilder()
            kb_builder.row(BatStoreCallback.create(level=0).get_back_button(language, 0))
            return get_text(language, BotEntity.USER, "batstore_not_found"), kb_builder

        sym = config.CURRENCY.get_localized_symbol()
        user = await UserRepository.get_by_tgid(callback.from_user.id, session)
        balance = round((user.top_up_amount or 0) - (user.consume_records or 0), 2)
        delivery_raw = product.delivery_type or "stock"
        delivery_labels = {
            "stock": "Instant Delivery ⚡",
            "supplier_api": "Instant Delivery ⚡",
            "activation": "Custom Activation ⏳",
        }
        delivery = delivery_labels.get(delivery_raw, delivery_raw.title())
        is_oos = RestockNotificationService.is_batstore_out_of_stock(product)
        if is_oos:
            await RestockNotificationService.auto_subscribe_if_out_of_stock(
                telegram_id=callback.from_user.id,
                user_id=user.id if user else None,
                product=product,
                language=language,
                session=session
            )
            await session_commit(session)

        icon_html = format_product_icon(product)
        display_name = f"🔴 {icon_html} {escape(product.name)} {get_text(language, BotEntity.USER, 'product_out_of_stock_badge')}" if is_oos else f"{icon_html} {escape(product.name)}"
        caption = get_text(language, BotEntity.USER, "batstore_detail").format(
            name=display_name,
            description=escape(clean_tg_emojis(product.description) or ""),
            price=f"{BatStoreStoreService._effective_price(product, user):.2f}" if product.sell_price_usd is not None else "-",
            sym=sym,
            delivery=delivery,
            stock=f"🔴 0 {get_text(language, BotEntity.USER, 'batstore_out_of_stock')}\n\n{get_text(language, BotEntity.USER, 'restock_auto_subscribed_notice')}" if is_oos else (product.stock if product.stock is not None else 0),
            balance=f"{balance:.2f}",
        )

        kb_builder = InlineKeyboardBuilder()
        if not is_oos and BatStoreStoreService._requires_mini_app(product):
            guidance, kb_builder = BatStoreStoreService._mini_app_checkout(product, language)
            return caption + "\n\n" + guidance, kb_builder
        if is_oos:
            is_sub = await RestockNotificationService.is_subscribed(
                telegram_id=callback.from_user.id,
                product_id=product.product_id,
                session=session
            )
            toggle_btn_text = (
                get_text(language, BotEntity.USER, "restock_unsubscribe_btn")
                if is_sub
                else get_text(language, BotEntity.USER, "restock_subscribe_btn")
            )
            kb_builder.button(
                text=toggle_btn_text,
                callback_data=RestockCallback.create(
                    product_id=product.product_id,
                    action="toggle"
                ).pack()
            )
        else:
            effective_unit = BatStoreStoreService._effective_price(product, user)
            max_qty = BatStoreStoreService._max_qty(product, balance, effective_unit)
            for qty in range(1, min(10, max_qty) + 1):
                kb_builder.button(
                    text=f"{qty}",
                    callback_data=BatStoreCallback.create(level=2, product_id=product.product_id, quantity=qty).pack()
                )
            kb_builder.adjust(5)
        kb_builder.row(BatStoreCallback.create(level=0).get_back_button(language, 0))
        return caption, kb_builder

    @staticmethod
    def _max_qty(product: BatStoreProduct, balance: float, unit_price: float | None = None) -> int:
        if product.delivery_type == "stock":
            stock = product.stock or 0
            if stock <= 0:
                return 0
        elif not (product.stock and product.stock > 0):
            pass
        pr = unit_price if unit_price is not None else (product.sell_price_usd or 0.0)
        if pr > 0 and balance > 0:
            return max(1, int(balance // pr))
        return 99

    @staticmethod
    async def confirm_one(callback: CallbackQuery,
                          callback_data: BatStoreCallback,
                          state: FSMContext,
                          session: AsyncSession | Session,
                          language: Language) -> tuple[str, InlineKeyboardBuilder]:
        product = await BatStoreProductRepository.get_by_product_id(callback_data.product_id, session)
        if product is None or product.hidden:
            kb = InlineKeyboardBuilder()
            kb.row(BatStoreCallback.create(level=0).get_back_button(language, 0))
            return get_text(language, BotEntity.USER, "batstore_not_found"), kb
        if BatStoreStoreService._requires_mini_app(product):
            return BatStoreStoreService._mini_app_checkout(product, language)
        sym = config.CURRENCY.get_localized_symbol()
        user = await UserRepository.get_by_tgid(callback.from_user.id, session)
        balance = round((user.top_up_amount or 0) - (user.consume_records or 0), 2)
        data = await state.get_data()
        cart: dict[int, int] = data.get(CART_KEY, {})
        cart[product.product_id] = callback_data.quantity
        await state.update_data({CART_KEY: cart})

        from services.user import get_vip_tier_info
        tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0), getattr(user, "custom_discount_pct", None))
        kb_builder = InlineKeyboardBuilder()
        try:
            total = await BatStoreStoreService._quoted_total(product, user, callback_data.quantity, session)
        except ValueError:
            kb_builder.button(text=get_text(language, BotEntity.COMMON, "back_button"),
                              callback_data=BatStoreCallback.create(level=1,
                                                                    product_id=product.product_id).pack())
            return get_text(language, BotEntity.USER, "batstore_not_found"), kb_builder
        discount_note = ""
        if discount_pct > 0:
            disc_val = round(callback_data.quantity * product.sell_price_usd - total, 2)
            if disc_val > 0:
                discount_note = f"\n🎖️ {tier_label}: -{discount_pct:.0f}% (-{disc_val:.2f}{sym})"
        caption = ""
        if not callback_data.confirmation:
            caption = get_text(language, BotEntity.USER, "batstore_added").format(
                qty=callback_data.quantity, name=escape(product.name))
        confirm_caption = get_text(language, BotEntity.USER, "batstore_buy_confirm").format(
            items=f"{callback_data.quantity} × {escape(product.name)} = {total}{sym}",
            total=f"{total}",
            sym=sym,
            balance=f"{balance}",
        ) + discount_note

        kb_builder.button(text=get_text(language, BotEntity.COMMON, "buy_now"),
                          callback_data=BatStoreCallback.create(level=3,
                                                                product_id=product.product_id,
                                                                quantity=callback_data.quantity,
                                                                confirmation=True).pack())
        kb_builder.button(text=get_text(language, BotEntity.COMMON, "back_button"),
                          callback_data=BatStoreCallback.create(level=1,
                                                                product_id=product.product_id).pack())
        return (caption + "\n\n" + confirm_caption).strip(), kb_builder

    # ------------------------------------------------------------- checkout

    @staticmethod
    async def checkout(callback: CallbackQuery,
                       callback_data: BatStoreCallback,
                       state: FSMContext,
                       session: AsyncSession | Session,
                       language: Language) -> tuple[str, InlineKeyboardBuilder]:
        user = await UserRepository.get_by_tgid(callback.from_user.id, session)
        product = await BatStoreProductRepository.get_by_product_id(callback_data.product_id, session)
        kb_builder = InlineKeyboardBuilder()
        kb_builder.row(BatStoreCallback.create(level=0).get_back_button(language, 0))
        if product is None or product.hidden:
            return get_text(language, BotEntity.USER, "batstore_not_found"), kb_builder

        sym = config.CURRENCY.get_localized_symbol()
        qty = callback_data.quantity or 1
        balance = round((user.top_up_amount or 0) - (user.consume_records or 0), 2)

        if callback_data.confirmation is False:
            kb_builder.row(callback_data.get_back_button(language, 0))
            return get_text(language, BotEntity.USER, "purchase_confirmation_declined"), kb_builder

        if BatStoreStoreService._requires_mini_app(product):
            return BatStoreStoreService._mini_app_checkout(product, language)
        message = callback.message
        # Telegram issues a new callback ID for each tap. The confirmation message
        # identifies the customer's purchase intent across retries and restarts.
        key_data = f"{callback.bot.id}:{message.chat.id}:{message.message_id}:{product.product_id}:{qty}"
        key = "bot_" + hashlib.sha256(key_data.encode()).hexdigest()
        from services.checkout import CheckoutService
        from services.order_fulfillment import FulfillmentService
        try:
            order, created = await CheckoutService.reserve(callback.from_user.id,
                {"product_id": product.product_id, "quantity": qty}, key, session)
        except HTTPException as exc:
            await session.rollback()
            if exc.detail == "insufficient_balance":
                total = await BatStoreStoreService._quoted_total(product, user, qty, session)
                return get_text(language, BotEntity.USER, "batstore_insufficient").format(
                    need=f"{total:.2f}", balance=f"{balance:.2f}", sym=sym), kb_builder
            return get_text(language, BotEntity.USER, "batstore_failed"), kb_builder

        order_id = order.id
        try:
            order = await FulfillmentService.fulfill_order(order_id, session)
            await session_commit(session)
        except Exception:
            # The committed order owns the debit and recovery. A timeout must not
            # manufacture a refund while the supplier may have accepted delivery.
            logging.exception("Bot fulfillment interrupted for order %s", order_id)
            await session.rollback()
            return f"Order #{order_id}\n" + get_text(language, BotEntity.USER, "batstore_activation_pending"), kb_builder
        result = CheckoutService.response(order)
        goods_list = result["goods"]
        total = result["total_paid"]
        await state.update_data({CART_KEY: {}})

        delivery_info = ""
        if goods_list:
            from routes.common import normalize_delivery_good
            goods_str = "\n".join(f"• <code>{escape(normalize_delivery_good(g))}</code>" for g in goods_list[:20])
            delivery_info = f"📦 <b>Your goods:</b>\n{goods_str}\n\n<i>(Tap any key above to copy)</i>"
        elif result["reseller_status"] == "failed":
            return f"Order #{order_id}\n" + get_text(language, BotEntity.USER, "batstore_failed"), kb_builder
        else:
            delivery_info = get_text(language, BotEntity.USER, "batstore_activation_pending")
        caption = get_text(language, BotEntity.USER, "batstore_success").format(
            items=f"{qty} × {escape(product.name)} = {total}{sym}",
            delivery_info=delivery_info,
        )
        if created:
            try:
                await NotificationService.send_to_admins(
                    f"🛒 New GH Store order #{order_id}\n"
                    f"tg:{callback.from_user.id} · {qty}×{escape(product.name)} · {total}{sym} · {escape(product.delivery_type)}",
                    None)
            except Exception:
                logging.exception("Could not notify admins for order %s", order_id)
        return caption, kb_builder
