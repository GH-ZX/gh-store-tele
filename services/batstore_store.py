import logging
import uuid

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from enums.bot_entity import BotEntity
from callbacks import BatStoreCallback, RestockCallback
from db import session_commit
from services.restock_notification import RestockNotificationService
from enums.language import Language
from models.batstore_order import BatStoreOrderDTO
from models.batstore_product import BatStoreProduct, format_product_icon
from repositories.batstore_order import BatStoreOrderRepository
from repositories.batstore_product import BatStoreProductRepository
from repositories.user import UserRepository
from services.batstore import BatStoreService
from services.notification import NotificationService
from utils.utils import get_text
from utils.telegram import clean_tg_emojis

CART_KEY = "batstore_cart"
PAGE_SIZE = 8


class BatStoreStoreService:

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
        display_name = f"🔴 {icon_html} {product.name} {get_text(language, BotEntity.USER, 'product_out_of_stock_badge')}" if is_oos else f"{icon_html} {product.name}"
        caption = get_text(language, BotEntity.USER, "batstore_detail").format(
            name=display_name,
            description=clean_tg_emojis(product.description),
            price=f"{product.sell_price_usd:.2f}" if product.sell_price_usd is not None else "-",
            sym=sym,
            delivery=delivery,
            stock=f"🔴 0 {get_text(language, BotEntity.USER, 'batstore_out_of_stock')}\n\n{get_text(language, BotEntity.USER, 'restock_auto_subscribed_notice')}" if is_oos else (product.stock if product.stock is not None else 0),
            balance=f"{balance:.2f}",
        )

        kb_builder = InlineKeyboardBuilder()
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
            max_qty = BatStoreStoreService._max_qty(product, balance)
            for qty in range(1, min(10, max_qty) + 1):
                kb_builder.button(
                    text=f"{qty}",
                    callback_data=BatStoreCallback.create(level=2, product_id=product.product_id, quantity=qty).pack()
                )
            kb_builder.adjust(5)
        kb_builder.row(BatStoreCallback.create(level=0).get_back_button(language, 0))
        return caption, kb_builder

    @staticmethod
    def _max_qty(product: BatStoreProduct, balance: float) -> int:
        if product.delivery_type == "stock":
            stock = product.stock or 0
            if stock <= 0:
                return 0
        elif not (product.stock and product.stock > 0):
            # supplier/activation with no stock info -> allow some
            pass
        if product.sell_price_usd and product.sell_price_usd > 0 and balance > 0:
            return max(1, int(balance // product.sell_price_usd))
        return 99

    @staticmethod
    async def confirm_one(callback: CallbackQuery,
                          callback_data: BatStoreCallback,
                          state: FSMContext,
                          session: AsyncSession | Session,
                          language: Language) -> tuple[str, InlineKeyboardBuilder]:
        product = await BatStoreProductRepository.get_by_product_id(callback_data.product_id, session)
        sym = config.CURRENCY.get_localized_symbol()
        user = await UserRepository.get_by_tgid(callback.from_user.id, session)
        balance = round((user.top_up_amount or 0) - (user.consume_records or 0), 2)
        data = await state.get_data()
        cart: dict[int, int] = data.get(CART_KEY, {})
        cart[product.product_id] = callback_data.quantity
        await state.update_data({CART_KEY: cart})

        from services.user import get_vip_tier_info
        from services.sale_pricing import price_lines
        tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0), getattr(user, "custom_discount_pct", None))
        try:
            (total_dec,), _ = price_lines(
                [(product.sell_price_usd, product.cost_usd, callback_data.quantity, 0)],
                discount_pct=discount_pct)
        except ValueError:
            return get_text(language, BotEntity.USER, "batstore_not_found"), kb_builder
        total = float(total_dec)
        discount_note = ""
        if discount_pct > 0:
            disc_val = round(callback_data.quantity * product.sell_price_usd - total, 2)
            if disc_val > 0:
                discount_note = f"\n🎖️ {tier_label}: -{discount_pct:.0f}% (-{disc_val:.2f}{sym})"
        caption = ""
        if not callback_data.confirmation:
            caption = get_text(language, BotEntity.USER, "batstore_added").format(
                qty=callback_data.quantity, name=product.name)
        confirm_caption = get_text(language, BotEntity.USER, "batstore_buy_confirm").format(
            items=f"{callback_data.quantity} × {product.name} = {total}{sym}",
            total=f"{total}",
            sym=sym,
            balance=f"{balance}",
        ) + discount_note

        kb_builder = InlineKeyboardBuilder()
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
        from services.user import get_vip_tier_info as _vip_info
        from services.sale_pricing import price_lines as _price_lines
        tier_label, discount_pct = _vip_info(getattr(user, "consume_records", 0.0))
        try:
            (total_dec,), _ = _price_lines(
                [(product.sell_price_usd, product.cost_usd, qty, 0)],
                discount_pct=discount_pct)
        except ValueError:
            return get_text(language, BotEntity.USER, "batstore_not_found"), kb_builder
        total = float(total_dec)
        balance = round((user.top_up_amount or 0) - (user.consume_records or 0), 2)

        if callback_data.confirmation is False:
            kb_builder.row(callback_data.get_back_button(language, 0))
            return get_text(language, BotEntity.USER, "purchase_confirmation_declined"), kb_builder

        debited = await UserRepository.try_debit_balance(callback.from_user.id, total, session)
        if not debited:
            caption = get_text(language, BotEntity.USER, "batstore_insufficient").format(
                need=f"{total}",
                balance=f"{balance}",
                sym=sym,
            )
            kb_builder.row(callback_data.get_back_button(language, 0))
            return caption, kb_builder
        await session_commit(session)

        customer_reference = f"ghstore-{callback.from_user.id}-{uuid.uuid4().hex[:8]}"
        try:
            quote = await BatStoreService.quote(session, product.product_id, qty)
        except Exception as e:
            logging.error("BatStore quote failed: %s", e)
            await UserRepository.refund_balance(callback.from_user.id, total, session)
            await session_commit(session)
            return get_text(language, BotEntity.USER, "batstore_failed"), kb_builder

        order_payload = {}
        order_payload["details"] = [{
            "product_id": product.product_id,
            "name": product.name,
            "quantity": qty,
            "cost_usd": product.cost_usd,
            "sell_usd": total,
            "delivery_type": product.delivery_type,
        }]
        external_ref = None
        try:
            placed = await BatStoreService.place_order(
                session, product.product_id, qty,
                customer_reference=customer_reference,
                idempotency_key=customer_reference,
            )
            external_ref = placed.get("order", {}).get("id") or placed.get("order_id")
        except Exception as e:
            logging.error("BatStore place_order failed: %s", e)
            await UserRepository.refund_balance(callback.from_user.id, total, session)
            await session_commit(session)
            return get_text(language, BotEntity.USER, "batstore_failed"), kb_builder
        order_status = "completed"
        if product.delivery_type in ("activation",):
            order_status = "pending_fulfillment"

        await BatStoreOrderRepository.create(BatStoreOrderDTO(
            telegram_id=callback.from_user.id,
            total_sell=total,
            status=order_status,
            external_order_ref=str(external_ref) if external_ref else None,
            customer_reference=customer_reference,
            details=order_payload["details"],
        ), session)
        await session_commit(session)

        await state.update_data({CART_KEY: {}})

        delivery_info = ""
        if product.delivery_type in ("stock", "supplier_api"):
            goods = placed.get("order", {}) or {}
            items = goods.get("items") or []
            if items:
                goods_list = "\n".join(f"• <code>{it.get('value') or it.get('data') or it}</code>" for it in items[:20])
                delivery_info = f"📦 <b>Your goods:</b>\n{goods_list}\n\n<i>(Tap any key above to copy)</i>"
            else:
                delivery_info = get_text(language, BotEntity.USER, "batstore_activation_pending")
        else:
            delivery_info = get_text(language, BotEntity.USER, "batstore_activation_pending")

        caption = get_text(language, BotEntity.USER, "batstore_success").format(
            items=f"{qty} × {product.name} = {total}{sym}",
            delivery_info=delivery_info,
        )
        await NotificationService.send_to_admins(
            f"🛒 New GH Store order\n"
            f"tg:{callback.from_user.id} · {qty}×{product.name} · {total}{sym} · {product.delivery_type}",
            None)
        return caption, kb_builder
