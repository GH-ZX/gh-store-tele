import uuid

import config
import db
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from callbacks import AllCategoriesCallback
from enums.bot_entity import BotEntity
from enums.entity_type import EntityType
from enums.keyboard_button import KeyboardButton as KB
from enums.language import Language
from handlers.common.common import enable_search
from handlers.user.constants import UserStates
from repositories.batstore_product import BatStoreProductRepository
from repositories.batstore_order import BatStoreOrderRepository
from repositories.user import UserRepository
from services.batstore import BatStoreService
from services.cart import CartService
from services.category import CategoryService
from services.config import ConfigService
from services.item import ItemService
from services.notification import NotificationService
from services.subcategory import SubcategoryService
from utils.custom_filters import IsUserExistFilter
from utils.utils import get_text

all_categories_router = Router()


@all_categories_router.message(F.text.in_(KB.get_localized_set(KB.ALL_CATEGORIES)), IsUserExistFilter())
async def all_categories_text_message(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    await all_types(callback=message, session=session, state=state, language=language)


async def all_types(**kwargs):
    """Entry point for 'All Categories' — skip item types, go straight to categories."""
    message: CallbackQuery | Message = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")
    # Jump directly to the categories view (level 1)
    if callback_data is None:
        callback_data = AllCategoriesCallback.create(1)
    new_data = callback_data.model_copy(update={"level": 1, "item_type": None})
    media, kb_builder = await CategoryService.get_buttons(new_data, state, session, language)
    caption = media.caption if hasattr(media, 'caption') else str(media)
    if isinstance(message, Message):
        await message.answer(text=caption, reply_markup=kb_builder.as_markup())
    else:
        callback: CallbackQuery = message
        try:
            await callback.message.edit_text(text=caption, reply_markup=kb_builder.as_markup())
        except Exception:
            await callback.message.edit_media(media=media, reply_markup=kb_builder.as_markup())


async def all_categories(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")

    # --- BatStore category: show products ---
    if callback_data.batstore_category_name:
        await _batstore_products_in_category(callback, callback_data, state, session, language)
        return

    state_data = await state.get_data()
    if callback_data.is_filter_enabled and state_data.get('filter') is not None:
        media, kb_builder = await CategoryService.get_buttons(callback_data, state, session, language)
    elif callback_data.is_filter_enabled:
        item_type_value = callback_data.item_type.value if callback_data.item_type else None
        media, kb_builder = await enable_search(callback_data,
                                                EntityType.CATEGORY,
                                                {"item_type": item_type_value},
                                                state,
                                                UserStates.filter_items,
                                                language)
    else:
        await state.update_data(filter=None)
        await state.set_state()
        media, kb_builder = await CategoryService.get_buttons(callback_data, state, session, language)
    await callback.message.edit_media(media=media, reply_markup=kb_builder.as_markup())


async def show_subcategories_in_category(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")

    # --- BatStore: show products in category ---
    if callback_data.batstore_category_name and not callback_data.batstore_product_id:
        await _batstore_products_in_category(callback, callback_data, state, session, language)
        return
    # --- BatStore: product detail ---
    if callback_data.batstore_product_id:
        await _batstore_product_detail(callback, callback_data, state, session, language)
        return

    state_data = await state.get_data()
    if callback_data.is_filter_enabled and state_data.get('filter') is not None:
        media, kb_builder = await SubcategoryService.get_buttons(callback_data, state, session, language)
    elif callback_data.is_filter_enabled:
        item_type_value = callback_data.item_type.value if callback_data.item_type else None
        media, kb_builder = await enable_search(callback_data,
                                                EntityType.SUBCATEGORY,
                                                {"category_id": callback_data.category_id,
                                                 "item_type": item_type_value},
                                                state,
                                                UserStates.filter_items,
                                                language)
    else:
        await state.update_data(filter=None)
        await state.set_state()
        media, kb_builder = await SubcategoryService.get_buttons(callback_data, state, session, language)
    await callback.message.edit_media(media=media, reply_markup=kb_builder.as_markup())


async def select_quantity(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")

    # BatStore confirm purchase
    if callback_data.batstore_product_id:
        await _batstore_confirm(callback, callback_data, state, session, language)
        return

    media, kb_builder = await SubcategoryService.get_select_quantity_buttons(callback_data, session, language)
    await callback.message.edit_media(media=media, reply_markup=kb_builder.as_markup())


async def add_to_cart_confirmation(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")

    # BatStore checkout
    if callback_data.batstore_product_id:
        await _batstore_checkout(callback, callback_data, state, session, language)
        return

    msg, kb_builder = await SubcategoryService.get_add_to_cart_buttons(callback_data, session, language)
    await callback.message.edit_caption(caption=msg, reply_markup=kb_builder.as_markup())


async def add_to_cart(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")
    media, kb_builder = await CartService.add_to_cart(callback, callback_data, session, language)
    await callback.message.edit_media(media=media, reply_markup=kb_builder.as_markup())


@all_categories_router.message(IsUserExistFilter(), F.text, StateFilter(UserStates.filter_items))
async def receive_filter_message(message: Message, state: FSMContext, session: AsyncSession, language: Language):
    await state.update_data(filter=message.html_text)
    state_data = await state.get_data()
    entity_type = EntityType(state_data['entity_type'])
    if entity_type == EntityType.CATEGORY:
        media, kb_builder = await CategoryService.get_buttons(None, state, session, language)
    else:
        media, kb_builder = await SubcategoryService.get_buttons(None, state, session, language)
    await NotificationService.answer_media(message, media, kb_builder.as_markup())


@all_categories_router.callback_query(AllCategoriesCallback.filter(), IsUserExistFilter())
async def navigate_categories(callback: CallbackQuery,
                              callback_data: AllCategoriesCallback,
                              session: AsyncSession,
                              state: FSMContext,
                              language: Language):
    current_level = callback_data.level

    levels = {
        0: all_types,
        1: all_categories,
        2: show_subcategories_in_category,
        3: select_quantity,
        4: add_to_cart_confirmation,
        5: add_to_cart,
        # BatStore levels handled inside all_categories / show_subcategories_in_category
    }

    current_level_function = levels.get(current_level)
    if current_level_function is None:
        return

    kwargs = {
        "callback": callback,
        "session": session,
        "callback_data": callback_data,
        "state": state,
        "language": language
    }

    await current_level_function(**kwargs)


# =====================================================================
# BatStore product browsing (integrated into the All Categories flow)
# =====================================================================

PAGE_SIZE = 8
BATSTORE_CART_KEY = "batstore_cart"


def _sym() -> str:
    return config.CURRENCY.get_localized_symbol()


def _back_to_categories(language) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=AllCategoriesCallback.create(level=1).pack())


async def _safe_edit(message, text, reply_markup):
    """Try edit_text first, fall back to edit_media."""
    try:
        await message.edit_text(text=text, reply_markup=reply_markup)
    except Exception:
        try:
            from utils.utils import get_bot_photo_id
            await message.edit_media(
                media=InputMediaPhoto(media=get_bot_photo_id(), caption=text),
                reply_markup=reply_markup)
        except Exception:
            pass


async def _batstore_products_in_category(callback, callback_data, state, session, language):
    """Show BatStore products inside a category (level 1 → level 2)."""
    cat_name = callback_data.batstore_category_name
    page = callback_data.page or 0
    products = await BatStoreProductRepository.get_by_category(cat_name, session)
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
        kb.button(
            text=label,
            callback_data=AllCategoriesCallback.create(
                level=2, batstore_category_name=cat_name,
                batstore_product_id=p.product_id).pack())
    kb.adjust(1)

    # Pagination
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(
                text=get_text(language, BotEntity.COMMON, "pagination_previous"),
                callback_data=AllCategoriesCallback.create(
                    level=1, batstore_category_name=cat_name, page=page - 1).pack()))
        nav.append(InlineKeyboardButton(
            text=f"• {page + 1}/{total_pages} •",
            callback_data=AllCategoriesCallback.create(
                level=1, batstore_category_name=cat_name, page=page).pack()))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(
                text=get_text(language, BotEntity.COMMON, "pagination_next"),
                callback_data=AllCategoriesCallback.create(
                    level=1, batstore_category_name=cat_name, page=page + 1).pack()))
        kb.row(*nav)

    kb.row(_back_to_categories(language))
    caption = get_text(language, BotEntity.USER, "batstore_category_products").format(
        category=cat_name)
    try:
        await callback.message.edit_text(text=caption, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.edit_media(
            media=InputMediaPhoto(media='https://i.postimg.cc/cCPbmkbc/photo-2026-05-09-16-07-18.jpg', caption=caption),
            reply_markup=kb.as_markup())


async def _batstore_product_detail(callback, callback_data, state, session, language):
    """Show BatStore product detail with description, image, price, qty picker."""
    product = await BatStoreProductRepository.get_by_product_id(
        callback_data.batstore_product_id, session)
    cat_name = callback_data.batstore_category_name
    kb = InlineKeyboardBuilder()
    if product is None or product.hidden:
        kb.row(InlineKeyboardButton(
            text=get_text(language, BotEntity.COMMON, "back_button"),
            callback_data=AllCategoriesCallback.create(
                level=1, batstore_category_name=cat_name).pack()))
        await callback.message.edit_text(
            get_text(language, BotEntity.USER, "batstore_not_found"),
            reply_markup=kb.as_markup())
        return

    sym = _sym()
    user = await UserRepository.get_by_tgid(callback.from_user.id, session)
    balance = round((user.top_up_amount or 0) - (user.consume_records or 0), 2)
    delivery = product.delivery_type or "stock"

    # Build a rich detail caption
    desc = product.description or ""
    # Clean up tg-emoji tags for plain display
    import re
    desc = re.sub(r'<tg-emoji[^>]*>([^<]*)</tg-emoji>', r'\1', desc)
    desc = desc.strip()

    lines = [f"<b>{product.name}</b>"]
    if desc:
        lines.append(f"\n{desc}")
    lines.append(f"\n💲 Price: <b>{product.sell_price_usd:.2f}{sym}</b>")
    lines.append(f"📦 Delivery: {delivery}")
    if product.warranty_days:
        lines.append(f"🛡️ Warranty: {product.warranty_days} days")
    stock_txt = product.stock if product.stock is not None else 0
    lines.append(f"📦 Stock: {stock_txt}")
    lines.append(f"\n💰 Your balance: {balance:.2f}{sym}")
    caption = "\n".join(lines)

    # Quantity buttons
    max_qty = _max_qty(product, balance)
    for qty in range(1, min(10, max_qty) + 1):
        kb.button(
            text=str(qty),
            callback_data=AllCategoriesCallback.create(
                level=3, batstore_category_name=cat_name,
                batstore_product_id=product.product_id,
                quantity=qty).pack())
    kb.adjust(5)
    kb.row(InlineKeyboardButton(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=AllCategoriesCallback.create(
            level=1, batstore_category_name=cat_name).pack()))

    if product.image_url:
        try:
            await callback.message.edit_text(text=caption, reply_markup=kb.as_markup())
            # Send product image separately
            try:
                await callback.message.answer_photo(photo=product.image_url)
            except Exception:
                pass
            return
        except Exception:
            pass
    await callback.message.edit_text(text=caption, reply_markup=kb.as_markup())


def _max_qty(product, balance: float) -> int:
    if product.delivery_type == "stock":
        stock = product.stock or 0
        if stock <= 0:
            return 0
    if product.sell_price_usd and product.sell_price_usd > 0 and balance > 0:
        return max(1, int(balance // product.sell_price_usd))
    return 99


async def _batstore_confirm(callback, callback_data, state, session, language):
    """Confirm BatStore purchase (level 3)."""
    product = await BatStoreProductRepository.get_by_product_id(
        callback_data.batstore_product_id, session)
    cat_name = callback_data.batstore_category_name
    sym = _sym()
    user = await UserRepository.get_by_tgid(callback.from_user.id, session)
    balance = round((user.top_up_amount or 0) - (user.consume_records or 0), 2)
    qty = callback_data.quantity or 1
    total = round(qty * (product.sell_price_usd or 0), 2)

    # Store in cart
    data = await state.get_data()
    cart: dict = data.get(BATSTORE_CART_KEY, {})
    cart[product.product_id] = qty
    await state.update_data({BATSTORE_CART_KEY: cart})

    caption = get_text(language, BotEntity.USER, "batstore_buy_confirm").format(
        items=f"{qty} × {product.name} = {total}{sym}",
        total=f"{total}",
        sym=sym,
        balance=f"{balance}",
    )

    kb = InlineKeyboardBuilder()
    kb.button(
        text=get_text(language, BotEntity.COMMON, "buy_now"),
        callback_data=AllCategoriesCallback.create(
            level=4, batstore_category_name=cat_name,
            batstore_product_id=product.product_id,
            quantity=qty, confirmation=True).pack())
    kb.button(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=AllCategoriesCallback.create(
            level=2, batstore_category_name=cat_name,
            batstore_product_id=product.product_id).pack())
    await callback.message.edit_text(text=caption, reply_markup=kb.as_markup())


async def _batstore_checkout(callback, callback_data, state, session, language):
    """Execute BatStore checkout (level 4)."""
    user = await UserRepository.get_by_tgid(callback.from_user.id, session)
    product = await BatStoreProductRepository.get_by_product_id(
        callback_data.batstore_product_id, session)
    cat_name = callback_data.batstore_category_name
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=AllCategoriesCallback.create(
            level=1, batstore_category_name=cat_name).pack()))

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

    # Quote
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

    from models.batstore_order import BatStoreOrderDTO
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
    await db.session_commit(session)

    await state.update_data({BATSTORE_CART_KEY: {}})

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
