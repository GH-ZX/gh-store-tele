import traceback
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import ErrorEvent, Message, BufferedInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
import config
from config import SUPPORT_LINK
import os
import logging

log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

from bot import dp, main, redis
from enums.bot_entity import BotEntity
from enums.keyboard_button import KeyboardButton
from enums.language import Language
from handlers.common.review_management import review_management_router
from middleware.database import DBSessionMiddleware
from middleware.language import I18nMiddleware
from middleware.throttling_middleware import ThrottlingMiddleware
from models.user import UserDTO
from multibot import main as main_multibot
from handlers.user.cart import cart_router
from handlers.admin.admin import admin_router
from handlers.user.all_categories import all_categories_router

from handlers.user.stars import stars_router
from handlers.user.sam import sam_router
from handlers.user.search import search_router
from handlers.user.my_profile import my_profile_router
from repositories.button_media import ButtonMediaRepository
from repositories.user import UserRepository
from services.media import MediaService
from services.notification import NotificationService
from services.review import ReviewService
from services.user import UserService
from utils.custom_filters import IsUserExistFilter, IsUserBannedFilter
from utils.utils import get_bot_photo_id, get_text

main_router = Router()


@main_router.message(CommandStart())
@main_router.message(Command("help"))
async def start(message: Message, command: CommandObject, session: AsyncSession, language: Language):
    telegram_id = message.from_user.id
    await UserService.create_if_not_exist(UserDTO(
        telegram_username=message.from_user.username,
        telegram_id=telegram_id,
        language=language
    ), command.args if command else None, session)

    user = await UserRepository.get_by_tgid(telegram_id, session)
    balance = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2) if user else 0.0
    from services.user import get_vip_tier_info
    tier_label, discount_pct = get_vip_tier_info(user.consume_records if user else 0, getattr(user, "custom_discount_pct", None) if user else None)
    is_admin = telegram_id in config.ADMIN_ID_LIST

    tma_host = (config.WEBHOOK_HOST or "").strip().rstrip('/')
    from services.telegram_auth import generate_session_token
    auth_token = generate_session_token(telegram_id)
    tma_url = f"{tma_host}/app?tg_id={telegram_id}&auth_token={auth_token}" if tma_host else ""

    is_ar = (language == Language.AR)

    # 1. Update Telegram Client Menu Button to MiniApp
    if tma_url:
        try:
            menu_btn_text = "🛍️ المتجر" if is_ar else "🛍️ Shop"
            await message.bot.set_chat_menu_button(
                chat_id=telegram_id,
                menu_button=types.MenuButtonWebApp(text=menu_btn_text, web_app=types.WebAppInfo(url=tma_url))
            )
        except Exception:
            pass

    # 2. Build Welcome Text
    user_name = message.from_user.first_name or message.from_user.username or ("العميل" if is_ar else "Customer")
    if is_ar:
        welcome_caption = (
            f"👋 أهلاً بك <b>{user_name}</b> في متجر <b>GH Store</b> المعتمد!\n\n"
            f"💎 <b>رتبتك:</b> {tier_label}\n"
            f"💰 <b>الرصيد المتاح:</b> <code>${balance:.2f} USD</code>\n\n"
            f"🛍️ يمكنك تصفح المنتجات الرقمية، شحن الرصيد، ومتابعة طلباتك فورياً عبر المتجر السريع أدناه:"
        )
        btn_shop = "🛍️ فتح المتجر والتسوق"
        btn_wallet = "💳 شحن الرصيد"
        btn_orders = "📦 طلباتي وعملياتي"
        btn_support = "💬 الدعم الفني"
        btn_reviews = "⭐ تقييمات العملاء"
        btn_admin = "👑 لوحة المشرف"
    else:
        welcome_caption = (
            f"👋 Welcome <b>{user_name}</b> to <b>GH Store</b>!\n\n"
            f"💎 <b>Your Rank:</b> {tier_label}\n"
            f"💰 <b>Available Balance:</b> <code>${balance:.2f} USD</code>\n\n"
            f"🛍️ Explore our full digital catalog, manage your balance, and track orders directly in the WebApp below:"
        )
        btn_shop = "🛍️ Open Store WebApp"
        btn_wallet = "💳 Top Up Balance"
        btn_orders = "📦 My Orders"
        btn_support = "💬 Customer Support"
        btn_reviews = "⭐ Reviews"
        btn_admin = "👑 Admin Panel"

    # 3. Inline Launcher Markup (under photo)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    inline_kb = InlineKeyboardBuilder()
    if tma_url:
        inline_kb.button(text=btn_shop, web_app=types.WebAppInfo(url=tma_url))
        inline_kb.button(text=btn_wallet, web_app=types.WebAppInfo(url=f"{tma_url}&startapp=wallet"))
        inline_kb.button(text=btn_orders, web_app=types.WebAppInfo(url=f"{tma_url}&startapp=orders"))
        if is_admin:
            inline_kb.button(text=btn_admin, web_app=types.WebAppInfo(url=f"{tma_url}&startapp=admin_radar"))
        inline_kb.adjust(1, 2)

    # 4. Persistent Bottom Reply Keyboard
    keyboard = []
    if tma_url:
        keyboard.append([types.KeyboardButton(text=btn_shop, web_app=types.WebAppInfo(url=tma_url))])
        keyboard.append([
            types.KeyboardButton(text=btn_wallet, web_app=types.WebAppInfo(url=f"{tma_url}&startapp=wallet")),
            types.KeyboardButton(text=btn_orders, web_app=types.WebAppInfo(url=f"{tma_url}&startapp=orders"))
        ])
    keyboard.append([
        types.KeyboardButton(text=btn_reviews),
        types.KeyboardButton(text=btn_support)
    ])
    if is_admin and tma_url:
        keyboard.append([types.KeyboardButton(text=btn_admin, web_app=types.WebAppInfo(url=f"{tma_url}&startapp=admin_radar"))])

    start_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, keyboard=keyboard)
    bot_photo_id = get_bot_photo_id()

    try:
        await message.answer_photo(photo=bot_photo_id, caption=welcome_caption, reply_markup=inline_kb.as_markup(), parse_mode="HTML")
    except Exception:
        await message.answer(welcome_caption, reply_markup=inline_kb.as_markup(), parse_mode="HTML")

    await message.answer("👇 " + ("استخدم القائمة أدناه أو اضغط على المتجر للبدء:" if is_ar else "Use the menu below or tap Store to start:"), reply_markup=start_markup)

@main_router.callback_query(F.data == "trigger_search", IsUserExistFilter())
async def trigger_search_cb(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:
        pass
    from handlers.user.constants import UserStates
    await state.set_state(UserStates.search_query)
    await callback.message.answer(
        "🔍 <b>Search Digital Products & Services</b>\n\n"
        "Please send the product name or keyword you are looking for\n"
        "(e.g. <code>ChatGPT</code>, <code>Gemini</code>, <code>Claude</code>, <code>Netflix</code>, <code>VPN</code>):"
    )


@main_router.message(F.web_app_data)
async def handle_web_app_data(message: Message, session: AsyncSession, language: Language, state: FSMContext):
    """Process user interactions from the Telegram Mini App."""
    import json
    raw = message.web_app_data.data if message.web_app_data else "{}"
    try:
        data = json.loads(raw)
        action = data.get("action")

        if action == "buy_batstore":
            pid = int(data.get("product_id") or 0)
            qty = int(data.get("quantity") or 1)
            if pid:
                from callbacks import BatStoreCallback
                from services.batstore_store import BatStoreStoreService
                cb_data = BatStoreCallback.create(level=2, product_id=pid, quantity=qty)
                caption, kb = await BatStoreStoreService.confirm_one(message, cb_data, state, session, language)
                await message.answer(caption, reply_markup=kb.as_markup())

        elif action == "topup_prompt":
            from callbacks import MyProfileCallback
            from services.user import UserService
            cb_profile = MyProfileCallback.create(level=1)
            msg_text, kb = await UserService.get_top_up_buttons(cb_profile, language, session)
            await message.answer(msg_text, reply_markup=kb.as_markup())

        elif action == "open_rail":
            rail = data.get("rail")
            if rail == "stars":
                from callbacks import StarsCallback
                from handlers.user.stars import stars_pick
                dummy_cb = types.CallbackQuery(id="tma", from_user=message.from_user, chat_instance="", message=message)
                await stars_pick(dummy_cb, StarsCallback.create(level=0), language)
            elif rail == "sam":
                from callbacks import SamCallback
                from handlers.user.sam import sam_pick_provider
                dummy_cb = types.CallbackQuery(id="tma", from_user=message.from_user, chat_instance="", message=message)
                await sam_pick_provider(dummy_cb, SamCallback.create(level=0), session, language)
            else:
                from callbacks import MyProfileCallback
                from services.user import UserService
                cb_profile = MyProfileCallback.create(level=1)
                msg_text, kb = await UserService.get_top_up_buttons(cb_profile, language, session)
                await message.answer(msg_text, reply_markup=kb.as_markup())

        elif action == "claim_warranty":
            order_id = int(data.get("order_id") or 0)
            if order_id:
                from repositories.batstore_order import BatStoreOrderRepository
                order = await BatStoreOrderRepository.get_by_id(order_id, session)
                if order and order.telegram_id == message.from_user.id:
                    from handlers.user.my_profile import claim_warranty_handler
                    dummy_cb = types.CallbackQuery(id="tma", from_user=message.from_user, chat_instance="", message=message, data=f"claim_warranty_{order_id}")
                    await claim_warranty_handler(dummy_cb, session, language)

        elif action == "report_issue":
            order_id = int(data.get("order_id") or 0)
            from handlers.user.constants import UserStates
            await state.set_state(UserStates.order_issue)
            await message.answer(
                f"📝 <b>Report an Issue with Order #{order_id}</b>\n\n"
                "Please send a message describing what went wrong. Our team will review it immediately:"
            )
    except Exception as e:
        logging.warning("Error processing web_app_data: %s", e)

@main_router.message(F.text.in_(KeyboardButton.get_localized_set(KeyboardButton.FAQ)), IsUserExistFilter())
async def faq(message: Message, session: AsyncSession, language: Language):
    from services.config import ConfigService
    cfg_key = "FAQ_TEXT_AR" if language == Language.AR else "FAQ_TEXT_EN"
    fallback_text = get_text(language, BotEntity.USER, "faq_string")
    faq_text = await ConfigService.get(session, cfg_key, default=fallback_text) or fallback_text

    support_link = await ConfigService.get(session, "SUPPORT_LINK", default="https://t.me/ahmedghx") or "https://t.me/ahmedghx"
    support_user = await ConfigService.get(session, "SUPPORT_USERNAME", default="ahmedghx") or "ahmedghx"

    kb_builder = InlineKeyboardBuilder()
    tma_host = (config.WEBHOOK_HOST or "").strip().rstrip('/')
    if tma_host:
        from services.telegram_auth import generate_session_token
        from aiogram.types import WebAppInfo
        auth_tok = generate_session_token(message.from_user.id)
        kb_builder.button(text="🛍️ تصفح وشراء المنتجات (Mini App)" if language == Language.AR else "🛍️ Open Store WebApp",
                          web_app=WebAppInfo(url=f"{tma_host}/app?tg_id={message.from_user.id}&auth_token={auth_tok}"))
    kb_builder.button(text=f"💬 خدمة العملاء (@{support_user})" if language == Language.AR else f"💬 Support Contact (@{support_user})",
                      url=support_link)
    kb_builder.adjust(1)
    button_media = await ButtonMediaRepository.get_by_button(KeyboardButton.FAQ, session)
    media = MediaService.convert_to_media(button_media.media_id, caption=faq_text) if button_media and button_media.media_id else None
    if media:
        await NotificationService.answer_media(message, media, kb_builder.as_markup())
    else:
        await message.answer(faq_text, parse_mode="HTML", reply_markup=kb_builder.as_markup())


@main_router.message(F.text.in_(KeyboardButton.get_localized_set(KeyboardButton.HELP)), IsUserExistFilter())
async def support(message: Message, session: AsyncSession, language: Language):
    from services.config import ConfigService
    cfg_key = "HELP_TEXT_AR" if language == Language.AR else "HELP_TEXT_EN"
    fallback_text = get_text(language, BotEntity.USER, "help_string")
    help_text = await ConfigService.get(session, cfg_key, default=fallback_text) or fallback_text

    support_link = await ConfigService.get(session, "SUPPORT_LINK", default="https://t.me/ahmedghx") or "https://t.me/ahmedghx"
    support_user = await ConfigService.get(session, "SUPPORT_USERNAME", default="ahmedghx") or "ahmedghx"

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(text=f"💬 مراسلة الدعم الفني (@{support_user})" if language == Language.AR else f"💬 Contact Support (@{support_user})",
                      url=support_link)
    tma_host = (config.WEBHOOK_HOST or "").strip().rstrip('/')
    if tma_host:
        from services.telegram_auth import generate_session_token
        from aiogram.types import WebAppInfo
        auth_tok = generate_session_token(message.from_user.id)
        kb_builder.button(text="🛍️ فتح المتجر السريع" if language == Language.AR else "🛍️ Open Store",
                          web_app=WebAppInfo(url=f"{tma_host}/app?tg_id={message.from_user.id}&auth_token={auth_tok}"))
    kb_builder.adjust(1)

    button_media = await ButtonMediaRepository.get_by_button(KeyboardButton.HELP, session)
    media = MediaService.convert_to_media(button_media.media_id, caption=help_text) if button_media and button_media.media_id else None
    if media:
        await NotificationService.answer_media(message, media, kb_builder.as_markup())
    else:
        await message.answer(help_text, parse_mode="HTML", reply_markup=kb_builder.as_markup())

@main_router.message(F.text.in_(KeyboardButton.get_localized_set(KeyboardButton.REVIEWS)), IsUserExistFilter())
async def reviews(message: Message, session: AsyncSession, language: Language):
    media, kb_builder = await ReviewService.get_reviews_paginated(None, session, language)
    await NotificationService.answer_media(message, media, reply_markup=kb_builder.as_markup())


@main_router.error(F.update.message.as_("message"))
async def error_handler(event: ErrorEvent, message: Message):
    await message.answer("Oops, something went wrong!")
    traceback_str = traceback.format_exc()
    admin_notification = (
        f"Critical error caused by {event.exception}\n\n"
        f"Stack trace:\n{traceback_str}"
    )
    if len(admin_notification) > 4096:
        byte_array = bytearray(admin_notification, 'utf-8')
        admin_notification = BufferedInputFile(byte_array, "exception.txt")
    exc_name = type(event.exception).__name__ if event.exception else "Unknown"
    await NotificationService.send_error_to_admins(f"aiogram_err_{exc_name}", admin_notification, None)


throttling_middleware = ThrottlingMiddleware(redis)
users_routers = Router()
users_routers.include_routers(
    all_categories_router,
    my_profile_router,
    cart_router,
    review_management_router,

    stars_router,
    sam_router,
    search_router
)
users_routers.message.middleware(throttling_middleware)
users_routers.callback_query.middleware(throttling_middleware)
main_router.include_router(admin_router)
main_router.include_routers(users_routers)
main_router.message.middleware(DBSessionMiddleware())
main_router.callback_query.middleware(DBSessionMiddleware())
main_router.message.middleware(I18nMiddleware())
main_router.callback_query.middleware(I18nMiddleware())


@main_router.message(IsUserBannedFilter())
async def banned_message(message: Message, language: Language):
    await message.answer(text=get_text(language, BotEntity.COMMON, "banned"))


@main_router.callback_query(IsUserBannedFilter())
async def banned_message(callback: CallbackQuery, language: Language):
    banned_text = get_text(language, BotEntity.COMMON, "banned")
    if callback.message.text:
        await callback.message.edit_text(banned_text)
    else:
        await callback.message.delete()
        await callback.message.answer(banned_text)


if __name__ == '__main__':
    if config.MULTIBOT:
        main_multibot(main_router)
    else:
        dp.include_router(main_router)
        main()
