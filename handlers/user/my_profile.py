from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from callbacks import MyProfileCallback
from enums.bot_entity import BotEntity
from enums.entity_type import EntityType
from enums.keyboard_button import KeyboardButton as KB
from enums.language import Language
from handlers.common.common import enable_search
from handlers.user.constants import UserStates
from services.buy import BuyService
from services.notification import NotificationService
from services.payment import PaymentService
from services.referral import ReferralService
from services.user import UserService
from utils.custom_filters import IsUserExistFilter
from utils.utils import get_text

my_profile_router = Router()

from utils.telegram import safe_edit_message

@my_profile_router.message(F.text.in_(KB.get_localized_set(KB.MY_PROFILE)), IsUserExistFilter())
async def my_profile_text_message(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    await my_profile(message=message, session=session, state=state, language=language)


async def my_profile(**kwargs):
    message: Message | CallbackQuery = kwargs.get("message") or kwargs.get("callback")
    session: AsyncSession = kwargs.get("session")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")
    await state.clear()
    media, kb_builder = await UserService.get_my_profile_buttons(message.from_user.id, session, language)
    if isinstance(message, Message):
        await NotificationService.answer_media(message, media, kb_builder.as_markup())
    elif isinstance(message, CallbackQuery):
        callback = message
        await safe_edit_message(callback, media, kb_builder.as_markup())


async def top_up_balance(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    state: FSMContext = kwargs.get("state")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")
    await state.set_state()
    msg_text, kb_builder = await UserService.get_top_up_buttons(callback_data, language, session)
    await safe_edit_message(callback, msg_text, kb_builder.as_markup())


async def purchase_history(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")
    msg_text, kb_builder = await UserService.get_purchase_history_buttons(callback.from_user.id, callback_data,
                                                                          state, session, language)
    await safe_edit_message(callback, msg_text, kb_builder.as_markup())


async def get_purchase(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")
    msg, kb_builder = await BuyService.get_purchase(callback_data, session, language)
    methods_map = {
        (True, True): ("edit_caption", "caption"),
        (True, False): ("edit_media", "media"),
        (False, True): ("edit_text", "text"),
        (False, False): ("edit_media", "media"),
    }

    has_caption = bool(callback.message.caption)
    is_string = isinstance(msg, str)
    method_name, param_name = methods_map[(has_caption, is_string)]

    method = getattr(callback.message, method_name)
    await method(**{param_name: msg}, reply_markup=kb_builder.as_markup())


async def get_purchased_item(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    state: FSMContext = kwargs.get("state")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")
    state_data = await state.get_data()
    if callback_data.is_filter_enabled and state_data.get("filter") is not None:
        media, kb_builder = await BuyService.get_purchased_item(callback_data, state, session, language)
    elif callback_data.is_filter_enabled:
        media, kb_builder = await enable_search(callback_data, EntityType.SUBCATEGORY, callback_data.buy_id, state,
                                                UserStates.filter_purchase_history, language)
    else:
        await state.update_data(filter=None)
        await state.set_state()
        media, kb_builder = await BuyService.get_purchased_item(callback_data, state, session, language)
    await safe_edit_message(callback, media, kb_builder.as_markup())


async def create_payment(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    session: AsyncSession = kwargs.get("session")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")
    response, kb_builder = await PaymentService.create(callback, callback_data, state, session, language)
    await safe_edit_message(callback, response, kb_builder.as_markup())


async def edit_language(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    session: AsyncSession = kwargs.get("session")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    msg, kb_builder = await UserService.edit_language(callback.from_user.id, callback_data, session)
    await safe_edit_message(callback, msg, kb_builder.as_markup())


async def referral_system(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    session: AsyncSession = kwargs.get("session")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    language: Language = kwargs.get("language")
    msg, kb_builder = await ReferralService.view_statistics(callback, callback_data, session, language)
    await safe_edit_message(callback, msg, kb_builder.as_markup())


async def batstore_orders(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")
    from repositories.batstore_order import BatStoreOrderRepository
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from callbacks import MyProfileCallback

    orders = await BatStoreOrderRepository.get_by_telegram_id(
        callback.from_user.id, session, limit=10)

    kb_builder = InlineKeyboardBuilder()
    if not orders:
        caption = get_text(language, BotEntity.USER, "batstore_orders_empty")
    else:
        lines = []
        for o in orders:
            sym = config.CURRENCY.get_localized_symbol()
            status_emoji = "✅" if o.status == "completed" else "⏳" if o.status == "pending_fulfillment" else "❌"
            details = o.details or []
            product_names = ", ".join(d.get("name", "?") for d in details[:3])
            if len(details) > 3:
                product_names += f" +{len(details) - 3} more"
            lines.append(
                f"{status_emoji} #{o.id} · {product_names} · {o.total_sell:.2f}{sym}"
            )
            if o.status == "completed" and o.details:
                for d in o.details:
                    goods = d.get("delivery_goods", [])
                    if goods:
                        for g in goods[:5]:
                            lines.append(f"  📦 <code>{g}</code>")
                        if len(goods) > 5:
                            lines.append(f"  ... +{len(goods) - 5} more")
                        lines.append("  <i>(Tap credentials above to copy)</i>")
            if o.status == "completed" and not getattr(o, "warranty_claimed", False):
                has_warranty = any((d.get("warranty_days") or 0) > 0 for d in (o.details or []))
                if has_warranty:
                    lines.append("  🛡️ <i>Eligible for warranty replacement</i>")
                    kb_builder.button(
                        text=f"🛡️ Claim Warranty #{o.id}",
                        callback_data=f"claim_warranty_{o.id}")
        caption = "\n\n".join(lines)
    if orders:
        kb_builder.button(
            text="⚠️ Report Order Issue",
            callback_data="report_batstore_issue")
    kb_builder.button(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=MyProfileCallback.create(level=0))
    kb_builder.adjust(1)
    await safe_edit_message(callback, caption, kb_builder.as_markup())


@my_profile_router.message(IsUserExistFilter(), F.text, StateFilter(UserStates.filter_purchase_history))
async def receive_filter_message(message: Message, state: FSMContext, session: AsyncSession, language: Language):
    import re
    sanitized = re.sub(r'<[^>]+>', '', message.html_text or message.text or '')
    await state.update_data(filter=sanitized)
    media, kb_builder = await BuyService.get_purchased_item(None, state, session, language)
    await NotificationService.answer_media(message, media, kb_builder.as_markup())


@my_profile_router.message(IsUserExistFilter(), F.text, StateFilter(UserStates.top_up_amount))
async def receive_top_up_amount(message: Message,
                                state: FSMContext,
                                session: AsyncSession,
                                language: Language):
    media, kb_builder = await PaymentService.create(message,
                                                    None,
                                                    state,
                                                    session,
                                                    language)
    state_data = await state.get_data()
    if state_data.get("chat_id") and state_data.get("msg_id"):
        await message.bot.edit_message_media(chat_id=state_data.get("chat_id"),
                                             message_id=state_data.get("msg_id"),
                                             media=media,
                                             reply_markup=kb_builder.as_markup())
    else:
        await NotificationService.answer_media(message, media, kb_builder.as_markup())


@my_profile_router.callback_query(MyProfileCallback.filter(), IsUserExistFilter())
async def navigate(callback: CallbackQuery,
                   callback_data: MyProfileCallback,
                   session: AsyncSession,
                   state: FSMContext,
                   language: Language):
    current_level = callback_data.level
    try:
        await callback.answer()
    except Exception:
        pass

    levels = {
        0: my_profile,
        1: top_up_balance,
        2: create_payment,
        3: purchase_history,
        4: get_purchased_item,
        5: get_purchase,
        6: edit_language,
        7: referral_system,
        8: batstore_orders,
        9: pick_currency_preference,
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



async def pick_currency_preference(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")

    if callback_data.currency:
        user = await UserRepository.get_by_tgid(callback.from_user.id, session)
        if user:
            user.currency_preference = callback_data.currency
            await UserRepository.update(user, session)
            await session_commit(session)
        await my_profile(**kwargs)
        return

    kb = InlineKeyboardBuilder()
    currencies = [
        ("🇺🇸 USD ($)", "USD"),
        ("🇪🇺 EUR (€)", "EUR"),
        ("🇸🇾 SYP (ل.س)", "SYP"),
        ("⭐ Stars (XTR)", "XTR"),
    ]
    for label, code in currencies:
        kb.button(text=label, callback_data=MyProfileCallback.create(level=9, currency=code).pack())
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text=get_text(language, BotEntity.COMMON, "back_button"),
                                  callback_data=MyProfileCallback.create(level=0).pack()))

    text = (
        "💱 <b>Display Currency Preference</b>\n\n"
        "Choose how prices and balances are displayed in the shop.\n"
        "<i>(Note: All underlying balances remain securely denominated in USD).</i>"
    )
    await safe_edit_message(callback, text, kb.as_markup())


@my_profile_router.callback_query(F.data.startswith("claim_warranty_"), IsUserExistFilter())
async def claim_warranty_handler(callback: CallbackQuery, session: AsyncSession, language: Language):
    try:
        await callback.answer()
    except Exception:
        pass
    order_id = int(callback.data.split("_")[-1])
    from repositories.batstore_order import BatStoreOrderRepository
    order = await BatStoreOrderRepository.get_by_id(order_id, session)
    if not order or order.telegram_id != callback.from_user.id or order.status != "completed":
        await callback.message.answer("Order not found or ineligible for warranty.")
        return

    if getattr(order, "warranty_claimed", False):
        await callback.message.answer("A warranty claim has already been submitted for this order.")
        return

    details = order.details or []
    product_id = details[0].get("product_id") if details else None
    if not product_id:
        await callback.message.answer("Product info unavailable.")
        return

    replacement_ref = f"warranty-{order.id}-{callback.from_user.id}"
    try:
        from services.batstore import BatStoreService
        placed = await BatStoreService.place_order(
            session, product_id, 1,
            customer_reference=replacement_ref,
            idempotency_key=replacement_ref,
        )
        goods_obj = placed.get("order", {}) or {}
        items = goods_obj.get("items") or []
        goods_list = [it.get("value") or it.get("data") or str(it) for it in items] if items else []

        await BatStoreOrderRepository.mark_warranty_claimed(order.id, True, session)
        await session_commit(session)

        goods_text = "\n".join(f"• <code>{g}</code>" for g in goods_list[:5]) if goods_list else "Replacement credentials queued."
        msg = (
            f"✅ <b>Warranty Replacement Approved!</b>\n\n"
            f"• <b>Order:</b> #{order.id}\n"
            f"• <b>New Credentials:</b>\n{goods_text}\n\n"
            "<i>(Tap any credential above to copy it)</i>"
        )
        await NotificationService.send_to_admins(
            f"🛡️ Automated warranty replacement issued for order #{order.id} (tg:{callback.from_user.id})",
            None
        )
    except Exception as e:
        await BatStoreOrderRepository.mark_warranty_claimed(order.id, True, session)
        await session_commit(session)
        msg = (
            f"🛡️ <b>Warranty Claim Submitted for Order #{order.id}</b>\n\n"
            "Our support team has been notified and is preparing your replacement manually. You will receive it shortly."
        )
        await NotificationService.send_to_admins(
            f"🛡️ Manual warranty claim submitted for order #{order.id} (tg:{callback.from_user.id}): {e}",
            None
        )

    kb = InlineKeyboardBuilder()
    kb.button(text=get_text(language, BotEntity.COMMON, "back_button"), callback_data=MyProfileCallback.create(level=8).pack())
    await safe_edit_message(callback, msg, kb.as_markup())

@my_profile_router.callback_query(F.data == "report_batstore_issue", IsUserExistFilter())
async def report_issue_prompt(callback: CallbackQuery, state: FSMContext, language: Language):
    await state.set_state(UserStates.order_issue)
    kb = InlineKeyboardBuilder()
    kb.button(text=get_text(language, BotEntity.COMMON, "back_button"), callback_data=MyProfileCallback.create(level=8).pack())
    await callback.message.answer(
        "📝 <b>Report an Issue with an Order</b>\n\n"
        "Please send a message describing the issue. Include your <b>Order #</b> (e.g. <code>Order #42 key does not activate</code>).\n"
        "Our support team will investigate immediately:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@my_profile_router.message(IsUserExistFilter(), UserStates.order_issue, F.text)
async def receive_order_issue(message: Message, state: FSMContext, session: AsyncSession, language: Language):
    issue_text = (message.text or "").strip()
    await state.clear()
    username = f"@{message.from_user.username}" if message.from_user.username else "No username"
    user_id = message.from_user.id

    ticket_msg = (
        f"📩 <b>New Support Ticket: Order Issue</b>\n\n"
        f"• <b>From:</b> {username} (ID: <code>{user_id}</code>)\n"
        f"• <b>Message:</b>\n{issue_text}"
    )
    await NotificationService.send_to_admins(ticket_msg, None)

    kb = InlineKeyboardBuilder()
    kb.button(text=get_text(language, BotEntity.COMMON, "back_button"), callback_data=MyProfileCallback.create(level=8).pack())
    await message.answer(
        "✅ <b>Your issue has been reported!</b>\n\n"
        "Our team has received your ticket and will investigate shortly.",
        reply_markup=kb.as_markup()
    )
