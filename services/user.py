import datetime

from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaPhoto, InputMediaVideo, InputMediaAnimation
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import MyProfileCallback, AdminMenuCallback, StarsCallback, SamCallback
from db import session_commit
from enums.bot_entity import BotEntity
from enums.cryptocurrency import Cryptocurrency
from enums.keyboard_button import KeyboardButton
from enums.language import Language
from enums.sort_property import SortProperty
from enums.user_role import UserRole
from handlers.common.common import add_pagination_buttons, add_sorting_buttons, get_filters_settings
from models.user import User, UserDTO
from repositories.button_media import ButtonMediaRepository
from repositories.buy import BuyRepository
from repositories.cart import CartRepository
def get_vip_tier_info(consume_records: float | None, custom_discount_pct: float | None = None) -> tuple[str, float]:
    """Return (tier_label, discount_percent) based on lifetime spend or custom override."""
    if custom_discount_pct is not None and custom_discount_pct > 0:
        return f"VIP ({custom_discount_pct:.0f}%)", float(custom_discount_pct)
    spent = float(consume_records or 0.0)
    if spent >= 1000.0:
        return "Platinum VIP", 10.0
    elif spent >= 500.0:
        return "Gold VIP", 7.0
    elif spent >= 100.0:
        return "Silver VIP", 3.0
    return "Standard", 0.0


def format_currency_display(amount_usd: float, currency_code: str = "USD", syp_rate: float | None = None) -> str:
    """Format USD amount into user's preferred currency."""
    code = (currency_code or "USD").upper()
    if code == "EUR":
        eur_amt = amount_usd * 0.92
        return f"€{eur_amt:.2f}"
    elif code == "SYP":
        rate = float(syp_rate) if syp_rate else (1.0 / float(config.SAM_SYP_USD_RATE or 0.002551))
        if 0 < rate < 1.0:
            rate = 1.0 / rate
        syp_amt = round(amount_usd * rate)
        return f"{int(syp_amt):,} ل.س"
    elif code == "XTR":
        stars_rate = float(config.GHSTORE_STARS_TO_USD or 0.01)
        stars = int(amount_usd / stars_rate) if stars_rate > 0 else int(amount_usd * 100)
        return f"{stars} ⭐"
    return f"${amount_usd:.2f}"

from repositories.user import UserRepository
from services.media import MediaService
from services.config import ConfigService
from utils.utils import get_text


class UserService:

    @staticmethod
    async def create_if_not_exist(user_dto: UserDTO,
                                  referrer_code: str | None,
                                  session: AsyncSession | Session) -> None:
        user = await UserRepository.get_by_tgid(user_dto.telegram_id, session)
        match user:
            case None:
                referrer_user_dto = None
                if referrer_code:
                    referrer_user_dto = await UserRepository.get_by_referrer_code(referrer_code, session)
                if referrer_user_dto:
                    user_dto.referred_by_user_id = referrer_user_dto.id
                    user_dto.referred_at = datetime.datetime.now(tz=datetime.timezone.utc)
                user_id = await UserRepository.create(user_dto, session)
                await CartRepository.get_or_create(user_id, session)
                await session_commit(session)
            case _:
                update_user_dto = UserDTO(**user.model_dump())
                update_user_dto.can_receive_messages = True
                update_user_dto.telegram_username = user_dto.telegram_username
                update_user_dto.language = user_dto.language
                await UserRepository.update(update_user_dto, session)
                await session_commit(session)

    @staticmethod
    async def get(user_dto: UserDTO, session: AsyncSession | Session) -> User | None:
        return await UserRepository.get_by_tgid(user_dto.telegram_id, session)

    @staticmethod
    async def check_channel_membership(bot, user_id: int, channel_id: str | int | None = None) -> bool:
        """Check if a user is an active member/admin of the official announcement channel."""
        cid = channel_id or getattr(config, "ANNOUNCEMENT_CHANNEL_ID", None)
        if not cid or not bot:
            return False
        try:
            member = await bot.get_chat_member(chat_id=cid, user_id=user_id)
            status = getattr(member, "status", None)
            return status in ("member", "administrator", "creator")
        except Exception:
            return False

    @staticmethod
    async def get_my_profile_buttons(telegram_id: int,
                                     session: AsyncSession,
                                     language: Language) -> tuple[InputMediaPhoto |
                                                                  InputMediaVideo |
                                                                  InputMediaAnimation, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        user = await UserRepository.get_by_tgid(telegram_id, session)
        curr_pref = getattr(user, "currency_preference", "USD") or "USD"

        kb_builder.button(text=get_text(language, BotEntity.USER, "top_up_balance_button"),
                          callback_data=MyProfileCallback.create(level=1))
        kb_builder.button(text=get_text(language, BotEntity.USER, "purchase_history_button"),
                          callback_data=MyProfileCallback.create(level=3))
        kb_builder.button(text=get_text(language, BotEntity.USER, "batstore_orders_button"),
                          callback_data=MyProfileCallback.create(level=8))
        kb_builder.button(text=get_text(language, BotEntity.USER, "referral_button"),
                          callback_data=MyProfileCallback.create(level=7))
        kb_builder.button(text=get_text(language, BotEntity.USER, "language"),
                          callback_data=MyProfileCallback.create(level=6))
        kb_builder.button(text=f"💱 {curr_pref}",
                          callback_data=MyProfileCallback.create(level=9))
        kb_builder.adjust(2)

        tma_host = (config.WEBHOOK_HOST or "").strip().rstrip('/')
        if tma_host and tma_host.startswith("https://"):
            from aiogram.types import WebAppInfo, InlineKeyboardButton
            kb_builder.row(
                InlineKeyboardButton(
                    text="🛍️ متجر الويب (Mini App)",
                    web_app=WebAppInfo(url=f"{tma_host}/app")
                )
            )

        if user.telegram_id in config.ADMIN_ID_LIST:
            from callbacks import AdminMenuCallback
            from aiogram.types import InlineKeyboardButton
            kb_builder.row(
                InlineKeyboardButton(
                    text="👑 لوحة تحكم المسؤول (Admin Panel)",
                    callback_data=AdminMenuCallback.create(level=0).pack()
                )
            )

        fiat_balance = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
        total_spent = round(user.consume_records or 0.0, 2)
        custom_disc = getattr(user, "custom_discount_pct", None)
        tier_label, discount_pct = get_vip_tier_info(user.consume_records, custom_disc)
        display_bal = format_currency_display(fiat_balance, curr_pref)

        caption = (
            f"👤 <b>الملف الشخصي (Profile)</b>\n\n"
            f"• <b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
            f"• <b>اسم المستخدم:</b> @{user.telegram_username or 'none'}\n\n"
            f"💰 <b>الرصيد المتاح:</b> <b>${fiat_balance:.2f}</b>"
            + (f" <i>(≈ {display_bal})</i>\n" if curr_pref != "USD" else "\n")
            + f"🛒 <b>إجمالي المشتريات:</b> <b>${total_spent:.2f}</b>\n"
            f"🎖️ <b>الرتبة:</b> <b>{tier_label}</b>"
            + (f" (<b>-{discount_pct:.0f}%</b> خصم تلقائي)\n" if discount_pct > 0 else "\n")
        )

        button_media = await ButtonMediaRepository.get_by_button(KeyboardButton.MY_PROFILE, session)
        if button_media and button_media.media_id and not str(button_media.media_id).startswith("0AgAC"):
            try:
                media = MediaService.convert_to_media(button_media.media_id, caption=caption)
                return media, kb_builder
            except Exception:
                pass
        return caption, kb_builder

    @staticmethod
    async def _topup_enabled(session: AsyncSession | None,
                             env_value: bool,
                             config_key: str) -> bool:
        """Resolve a top-up toggle DB-first (admin panel), falling back to env."""
        if session is None:
            return env_value
        raw = await ConfigService.get(session, config_key,
                                      env_fallback="true" if env_value else "false",
                                      default="false")
        return isinstance(raw, str) and raw.strip().lower() in ("1", "true", "yes", "on")

    @staticmethod
    async def get_top_up_buttons(callback_data: MyProfileCallback,
                                 language: Language,
                                 session: AsyncSession | None = None) -> tuple[str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        for cryptocurrency in Cryptocurrency.get_visible():
            suffix = cryptocurrency.get_topup_suffix()
            enabled = await UserService._topup_enabled(
                session, getattr(config, f"TOPUP_ENABLE_{suffix}", False), f"TOPUP_ENABLE_{suffix}")
            if not enabled:
                continue
            kb_builder.button(
                text=cryptocurrency.get_localized(language),
                callback_data=MyProfileCallback.create(level=callback_data.level + 1,
                                                       cryptocurrency=cryptocurrency)
            )
        stars_enabled = await UserService._topup_enabled(
            session, config.GHSTORE_STARS_ENABLED, "GHSTORE_STARS_ENABLED")
        if stars_enabled:
            kb_builder.button(
                text=get_text(language, BotEntity.COMMON, "stars_button"),
                callback_data=StarsCallback.create(level=0)
            )
        if config.SAM_API_KEY:
            shamcash_enabled = await UserService._topup_enabled(
                session, config.TOPUP_ENABLE_SHAMCASH, "TOPUP_ENABLE_SHAMCASH")
            syriatel_enabled = await UserService._topup_enabled(
                session, config.TOPUP_ENABLE_SYRIATEL, "TOPUP_ENABLE_SYRIATEL")
            if shamcash_enabled or syriatel_enabled:
                kb_builder.button(
                    text=get_text(language, BotEntity.COMMON, "sam_button"),
                    callback_data=SamCallback.create(level=0)
                )
        kb_builder.adjust(1)
        kb_builder.row(callback_data.get_back_button(language))
        msg_text = get_text(language, BotEntity.USER, "choose_top_up_method")
        return msg_text, kb_builder

    @staticmethod
    async def get_purchase_history_buttons(telegram_id: int | None,
                                           callback_data: MyProfileCallback | None,
                                           state: FSMContext,
                                           session: AsyncSession,
                                           language: Language) -> tuple[str, InlineKeyboardBuilder]:
        callback_data = callback_data or MyProfileCallback.create(level=3)
        user_id = None
        if callback_data.user_role == UserRole.ADMIN:
            back_button = AdminMenuCallback.create(0).get_back_button(language, 0)
        else:
            user = await UserRepository.get_by_tgid(telegram_id, session)
            user_id = user.id
            back_button = callback_data.get_back_button(language, 0)
        sort_pairs, _ = await get_filters_settings(state, callback_data)
        buys = await BuyRepository.get_by_buyer_id(sort_pairs, user_id, callback_data.page, session)
        kb_builder = InlineKeyboardBuilder()
        for buy in buys:
            kb_builder.button(text=get_text(language, BotEntity.USER, "purchase_history_item").format(
                buy_id=buy.id,
                total_price=buy.total_price,
                currency_sym=config.CURRENCY.get_localized_symbol()),
                callback_data=MyProfileCallback.create(
                    level=callback_data.level + 1,
                    buy_id=buy.id,
                    user_role=callback_data.user_role
                ))
        kb_builder.adjust(1)
        kb_builder = await add_sorting_buttons(kb_builder, [SortProperty.TOTAL_PRICE,
                                                            SortProperty.BUY_DATETIME],
                                               callback_data, sort_pairs, language)
        kb_builder = await add_pagination_buttons(kb_builder, callback_data,
                                                  BuyRepository.get_max_page_purchase_history(user_id, session),
                                                  back_button, language)
        if len(kb_builder.as_markup().inline_keyboard) > 1 and callback_data.user_role == UserRole.USER:
            caption = get_text(language, BotEntity.USER, "purchases")
        elif len(kb_builder.as_markup().inline_keyboard) > 1 and callback_data.user_role == UserRole.ADMIN:
            caption = get_text(language, BotEntity.ADMIN, "pick_purchase")
        else:
            caption = get_text(language, BotEntity.USER, "no_purchases")
        return caption, kb_builder

    @staticmethod
    async def edit_language(telegram_id: int,
                            callback_data: MyProfileCallback,
                            session: AsyncSession) -> tuple[str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        default_language = Language.EN
        back_button = callback_data.get_back_button(default_language, 0)
        if callback_data.language is None:
            msg = get_text(default_language, BotEntity.USER, "edit_language")
            for language_object in Language:
                kb_builder.button(
                    text=f"{language_object.get_flag_emoji()} {language_object.name}",
                    callback_data=callback_data.model_copy(update={"language": language_object})
                )
            kb_builder.row(callback_data.get_back_button(default_language, 0))
        elif callback_data.language is not None and callback_data.confirmation is False:
            user_dto = await UserRepository.get_by_tgid(telegram_id, session)
            msg = get_text(default_language, BotEntity.USER, "edit_language_confirmation").format(
                current_language=user_dto.language.name,
                update_language=callback_data.language.name
            )
            kb_builder.button(
                text=get_text(default_language, BotEntity.COMMON, "confirm"),
                callback_data=callback_data.model_copy(update={"confirmation": True})
            )
            kb_builder.button(
                text=get_text(default_language, BotEntity.COMMON, "cancel"),
                callback_data=back_button.callback_data
            )
        else:
            user_dto = await UserRepository.get_by_tgid(telegram_id, session)
            user_dto.language = callback_data.language
            await UserRepository.update(user_dto, session)
            await session_commit(session)
            msg = get_text(default_language, BotEntity.USER, "language_edited_successfully")
            kb_builder.row(back_button)
        kb_builder.adjust(1)
        return msg, kb_builder
