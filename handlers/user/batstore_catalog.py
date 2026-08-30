"""BatStore catalog browsing integrated into the All Categories flow.

Navigation (using BatStoreCallback):
  Level 10 → category list
  Level 11 → product list inside a category  (carries category_name)
  Level 12 → product detail + quantity picker (carries product_id)
  Level 13 → confirm purchase
  Level 14 → checkout / result
"""

import uuid

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import config
from callbacks import BatStoreCallback
from db import session_commit
from enums.bot_entity import BotEntity
from enums.language import Language
from repositories.batstore_product import BatStoreProductRepository
from models.batstore_order import BatStoreOrderDTO
from repositories.batstore_order import BatStoreOrderRepository
from repositories.user import UserRepository
from services.batstore import BatStoreService
from services.notification import NotificationService
from utils.utils import get_text, get_bot_photo_id
from utils.custom_filters import IsUserExistFilter

batstore_catalog_router = Router(name="batstore_catalog")

PAGE_SIZE = 8
CART_KEY = "batstore_cart"


def _sym() -> str:
    return config.CURRENCY.get_localized_symbol()


def _back_to_categories(language) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=BatStoreCallback.create(level=10).pack())


# ------------------------------------------------ level 10: category list

@batstore_catalog_router.callback_query(
    BatStoreCallback.filter(F.level == 10), IsUserExistFilter())
async def batstore_categories(callback: CallbackQuery,
                               callback_data: BatStoreCallback,
                               session: AsyncSession,
                               language: Language):
    categories = await BatStoreProductRepository.get_categories(session)
    kb = InlineKeyboardBuilder()
    for cat in categories:
        count = await BatStoreProductRepository.get_category_product_count(cat, session)
        kb.button(
            text=f"{cat}  ({count})",
            callback_data=BatStoreCallback.create(level=11, category_name=cat).pack())
    kb.adjust(1)
    # Back to main menu (All Categories level 0)
    from callbacks import AllCategoriesCallback
    kb.row(InlineKeyboardButton(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=AllCategoriesCallback.create(level=0).pack()))
    caption = get_text(language, BotEntity.USER, "batstore_categories_title")
    media = InputMediaPhoto(media=get_bot_photo_id(), caption=caption)
    await callback.message.edit_media(media=media, reply_markup=kb.as_markup())


# ------------------------------------------------ level 11: product list in category

@batstore_catalog_router.callback_query(
    BatStoreCallback.filter(F.level == 11), IsUserExistFilter())
async def batstore_products_in_category(callback: CallbackQuery,
                                         callback_data: BatStoreCallback,
                                         session: AsyncSession,
                                         language: Language):
    cat_name = callback_data.category_name
    products = await BatStoreProductRepository.get_by_category(cat_name, session)
    page = callback_data.page or 0
    total_pages = max(1, (len(products) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages - 1)
    start = page * PAGE_SIZE
    slice_ = products[start:start + PAGE_SIZE]

    kb = InlineKeyboardBuilder()
    sym = _sym()
    for p in slice_:
        label = p.name
        if p.sell_price_usd is not None:
            label = f"{label} — {p.sell_price_usd:.2f}{sym}"
        if p.delivery_type == "stock" and not (p.stock and p.stock > 0):
            label += get_text(language, BotEntity.USER, "batstore_out_of_stock")
        elif p.delivery_type != "stock" and not (p.stock and p.stock > 0):
            label += f" ({p.stock if p.stock is not None else 0} left)"
        kb.button(
            text=label,
            callback_data=BatStoreCallback.create(
                level=12, product_id=p.product_id, category_name=cat_name).pack())
    kb.adjust(1)

    # Pagination
    if total_pages > 1:
        row = []
        if page > 0:
            row.append(kb.button(
                text=get_text(language, BotEntity.COMMON, "pagination_previous"),
                callback_data=BatStoreCallback.create(
                    level=11, category_name=cat_name, page=page - 1).pack()))
        row.append(kb.button(
            text=f"• {page + 1}/{total_pages} •",
            callback_data=BatStoreCallback.create(
                level=11, category_name=cat_name, page=page).pack()))
        if page < total_pages - 1:
            row.append(kb.button(
                text=get_text(language, BotEntity.COMMON, "pagination_next"),
                callback_data=BatStoreCallback.create(
                    level=11, category_name=cat_name, page=page + 1).pack()))
        kb.row(*row)

    kb.row(_back_to_categories(language))

    if not products:
        caption = get_text(language, BotEntity.USER, "batstore_empty")
    else:
        caption = get_text(language, BotEntity.USER, "batstore_category_products").format(
            category=cat_name)
    media = InputMediaPhoto(media=get_bot_photo_id(), caption=caption)
    await callback.message.edit_media(media=media, reply_markup=kb.as_markup())


# ------------------------------------------------ level 12: product detail + quantity

@batstore_catalog_router.callback_query(
    BatStoreCallback.filter(F.level == 12), IsUserExistFilter())
async def batstore_product_detail(callback: CallbackQuery,
                                   callback_data: BatStoreCallback,
                                   state: FSMContext,
                                   session: AsyncSession,
                                   language: Language):
    product = await BatStoreProductRepository.get_by_product_id(
        callback_data.product_id, session)
    cat_name = callback_data.category_name
    kb = InlineKeyboardBuilder()
    if product is None or product.hidden:
        kb.row(BatStoreCallback.create(level=11, category_name=cat_name).pack())
        await callback.message.edit_text(
            get_text(language, BotEntity.USER, "batstore_not_found"),
            reply_markup=kb.as_markup())
        return

    sym = _sym()
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

    max_qty = _max_qty(product, balance)
    for qty in range(1, min(10, max_qty) + 1):
        kb.button(
            text=str(qty),
            callback_data=BatStoreCallback.create(
                level=13, product_id=product.product_id,
                category_name=cat_name, quantity=qty).pack())
    kb.adjust(5)
    kb.row(BatStoreCallback.create(level=11, category_name=cat_name).pack())

    if product.image_url:
        media = InputMediaPhoto(media=product.image_url, caption=caption)
        await callback.message.edit_media(media=media, reply_markup=kb.as_markup())
    else:
        await callback.message.edit_text(text=caption, reply_markup=kb.as_markup())


def _max_qty(product, balance: float) -> int:
    if product.delivery_type == "stock":
        stock = product.stock or 0
        if stock <= 0:
            return 0
    if product.sell_price_usd and product.sell_price_usd > 0 and balance > 0:
        return max(1, int(balance // product.sell_price_usd))
    return 99


# ------------------------------------------------ level 13: confirm

@batstore_catalog_router.callback_query(
    BatStoreCallback.filter(F.level == 13), IsUserExistFilter())
async def batstore_confirm(callback: CallbackQuery,
                            callback_data: BatStoreCallback,
                            state: FSMContext,
                            session: AsyncSession,
                            language: Language):
    product = await BatStoreProductRepository.get_by_product_id(
        callback_data.product_id, session)
    cat_name = callback_data.category_name
    sym = _sym()
    user = await UserRepository.get_by_tgid(callback.from_user.id, session)
    balance = round((user.top_up_amount or 0) - (user.consume_records or 0), 2)
    qty = callback_data.quantity or 1
    total = round(qty * (product.sell_price_usd or 0), 2)

    # Store in cart
    data = await state.get_data()
    cart: dict = data.get(CART_KEY, {})
    cart[product.product_id] = qty
    await state.update_data({CART_KEY: cart})

    caption = get_text(language, BotEntity.USER, "batstore_buy_confirm").format(
        items=f"{qty} × {product.name} = {total}{sym}",
        total=f"{total}",
        sym=sym,
        balance=f"{balance}",
    )

    kb = InlineKeyboardBuilder()
    kb.button(
        text=get_text(language, BotEntity.COMMON, "buy_now"),
        callback_data=BatStoreCallback.create(
            level=14, product_id=product.product_id,
            category_name=cat_name, quantity=qty, confirmation=True).pack())
    kb.button(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=BatStoreCallback.create(
            level=12, product_id=product.product_id,
            category_name=cat_name).pack())
    await callback.message.edit_text(text=caption, reply_markup=kb.as_markup())


# ------------------------------------------------ level 14: checkout

@batstore_catalog_router.callback_query(
    BatStoreCallback.filter(F.level == 14), IsUserExistFilter())
async def batstore_checkout(callback: CallbackQuery,
                             callback_data: BatStoreCallback,
                             state: FSMContext,
                             session: AsyncSession,
                             language: Language):
    user = await UserRepository.get_by_tgid(callback.from_user.id, session)
    product = await BatStoreProductRepository.get_by_product_id(
        callback_data.product_id, session)
    cat_name = callback_data.category_name
    kb = InlineKeyboardBuilder()
    kb.row(BatStoreCallback.create(level=11, category_name=cat_name).pack())

    if product is None or product.hidden:
        await callback.message.edit_text(
            get_text(language, BotEntity.USER, "batstore_not_found"),
            reply_markup=kb.as_markup())
        return

    sym = _sym()
    qty = callback_data.quantity or 1
    total = round(qty * (product.sell_price_usd or 0), 2)
    balance = round((user.top_up_amount or 0) - (user.consume_records or 0), 2)

    if balance < total:
        caption = get_text(language, BotEntity.USER, "batstore_insufficient").format(
            need=f"{total}", balance=f"{balance}", sym=sym)
        await callback.message.edit_text(text=caption, reply_markup=kb.as_markup())
        return

    customer_reference = f"ghstore-{callback.from_user.id}-{uuid.uuid4().hex[:8]}"

    # Quote first
    try:
        await BatStoreService.quote(session, product.product_id, qty)
    except Exception:
        await callback.message.edit_text(
            get_text(language, BotEntity.USER, "batstore_failed"),
            reply_markup=kb.as_markup())
        return

    # Place order
    external_ref = None
    try:
        placed = await BatStoreService.place_order(
            session, product.product_id, qty,
            customer_reference=customer_reference,
            idempotency_key=customer_reference)
        external_ref = placed.get("order", {}).get("id") or placed.get("order_id")
    except Exception:
        await callback.message.edit_text(
            get_text(language, BotEntity.USER, "batstore_failed"),
            reply_markup=kb.as_markup())
        return

    # Charge customer
    user.consume_records = (user.consume_records or 0) + total
    await UserRepository.update(user, session)

    await BatStoreOrderRepository.create(
        BatStoreOrderDTO(
            telegram_id=callback.from_user.id,
            total_sell=total,
            status="completed",
            external_order_ref=str(external_ref) if external_ref else None,
            customer_reference=customer_reference,
            details=[{
                "product_id": product.product_id,
                "name": product.name,
                "quantity": qty,
                "cost_usd": product.cost_usd,
                "sell_usd": total,
                "delivery_type": product.delivery_type,
            }],
        ), session)
    await session_commit(session)

    await state.update_data({CART_KEY: {}})

    # Delivery info
    delivery_info = ""
    if product.delivery_type in ("stock", "supplier_api"):
        goods = placed.get("order", {}) or {}
        items = goods.get("items") or []
        if items:
            goods_list = "\n".join(
                f"• {it.get('value') or it.get('data') or it}" for it in items[:20])
            delivery_info = f"📦 Your goods:\n{goods_list}"
        else:
            delivery_info = get_text(language, BotEntity.USER, "batstore_activation_pending")
    else:
        delivery_info = get_text(language, BotEntity.USER, "batstore_activation_pending")

    caption = get_text(language, BotEntity.USER, "batstore_success").format(
        items=f"{qty} × {product.name} = {total}{sym}",
        delivery_info=delivery_info)

    await NotificationService.send_to_admins(
        f"🛒 New GH Store order\n"
        f"tg:{callback.from_user.id} · {qty}×{product.name} · {total}{sym} · {product.delivery_type}",
        None)
    await callback.message.edit_text(text=caption, reply_markup=kb.as_markup())
