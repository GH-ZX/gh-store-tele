import uuid

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from enums.bot_entity import BotEntity
from callbacks import BatStoreCallback
from db import session_commit
from enums.language import Language
from models.batstore_order import BatStoreOrderDTO
from models.batstore_product import BatStoreProduct
from repositories.batstore_order import BatStoreOrderRepository
from repositories.batstore_product import BatStoreProductRepository
from repositories.user import UserRepository
from services.batstore import BatStoreService
from services.notification import NotificationService
from utils.utils import get_text

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
            label = p.name
            if p.sell_price_usd is not None:
                label = f"{label} — {p.sell_price_usd:.2f}{sym}"
            if p.delivery_type == "stock" and not (p.stock and p.stock > 0):
                label += get_text(language, BotEntity.USER, "batstore_out_of_stock")
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
        delivery = product.delivery_type or "stock"
        caption = get_text(language, BotEntity.USER, "batstore_detail").format(
            name=product.name,
            description=product.description or "",
            price=f"{product.sell_price_usd:.2f}" if product.sell_price_usd is not None else "-",
            sym=sym,
            delivery=delivery,
            stock=product.stock if product.stock is not None else 0,
            balance=f"{balance:.2f}",
        )

        kb_builder = InlineKeyboardBuilder()
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

        total = round(callback_data.quantity * product.sell_price_usd, 2)
        caption = ""
        if not callback_data.confirmation:
            caption = get_text(language, BotEntity.USER, "batstore_added").format(
                qty=callback_data.quantity, name=product.name)
        confirm_caption = get_text(language, BotEntity.USER, "batstore_buy_confirm").format(
            items=f"{callback_data.quantity} × {product.name} = {total}{sym}",
            total=f"{total}",
            sym=sym,
            balance=f"{balance}",
        )

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
        total = round(qty * product.sell_price_usd, 2)
        balance = round((user.top_up_amount or 0) - (user.consume_records or 0), 2)

        if balance < total:
            caption = get_text(language, BotEntity.USER, "batstore_insufficient").format(
                need=f"{total}",
                balance=f"{balance}",
                sym=sym,
            )
            kb_builder.row(callback_data.get_back_button(language, 0))
            return caption, kb_builder

        if callback_data.confirmation is False:
            # do not double-charge; proceed to fulfill
            pass

        customer_reference = f"ghstore-{callback.from_user.id}-{uuid.uuid4().hex[:8]}"
        try:
            quote = await BatStoreService.quote(session, product.product_id, qty)
        except Exception:
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
        except Exception:
            return get_text(language, BotEntity.USER, "batstore_failed"), kb_builder

        # charge the customer balance only after the upstream order succeeded
        user.consume_records = (user.consume_records or 0) + total
        await UserRepository.update(user, session)

        await BatStoreOrderRepository.create(BatStoreOrderDTO(
            telegram_id=callback.from_user.id,
            total_sell=total,
            status="completed",
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
                goods_list = "\n".join(f"• {it.get('value') or it.get('data') or it}" for it in items[:20])
                delivery_info = f"📦 Your goods:\n{goods_list}"
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
