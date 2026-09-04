import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import config
from callbacks import StarsCallback, MyProfileCallback
from db import session_commit
from enums.bot_entity import BotEntity
from enums.language import Language
from repositories.user import UserRepository
from models.stars_payment import StarsPaymentDTO
from repositories.stars_payment import StarsPaymentRepository
from services.referral import ReferralService
from services.notification import NotificationService
from utils.custom_filters import IsUserExistFilter
from utils.utils import get_text

stars_router = Router(name="stars")

STAR_PRESETS = [25, 50, 100, 200, 500, 1000]


def get_rate() -> float:
    try:
        return float(config.GHSTORE_STARS_TO_USD or 0.01)
    except ValueError:
        return 0.01


def is_enabled() -> bool:
    return bool(config.GHSTORE_STARS_ENABLED)


def _back_to_menu(language: Language) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=MyProfileCallback.create(level=1).pack())


@stars_router.callback_query(StarsCallback.filter(F.level == 0), IsUserExistFilter())
async def stars_pick(callback: CallbackQuery, callback_data: StarsCallback,
                     language: Language):
    if not is_enabled():
        await callback.answer("Stars top-up is disabled.", show_alert=False)
        return
    kb_builder = InlineKeyboardBuilder()
    for stars in STAR_PRESETS:
        kb_builder.button(
            text=get_text(language, BotEntity.COMMON, "stars_amount_label").format(stars=stars),
            callback_data=StarsCallback.create(level=1, stars=stars).pack())
    kb_builder.adjust(3)
    kb_builder.row(_back_to_menu(language))
    await callback.message.edit_caption(
        caption=get_text(language, BotEntity.COMMON, "stars_pick_amount"),
        reply_markup=kb_builder.as_markup())


@stars_router.callback_query(StarsCallback.filter(F.level == 1), IsUserExistFilter())
async def stars_confirm(callback: CallbackQuery, bot: Bot, callback_data: StarsCallback,
                        language: Language):
    if not is_enabled() or not callback_data.stars:
        await callback.answer()
        return
    usd = round(callback_data.stars * get_rate(), 2)
    title = "GH Store balance top-up"
    description = f"{callback_data.stars} Telegram Stars -> {usd} {config.CURRENCY.get_localized_text()} balance"
    payload = f"stars:{callback.from_user.id}:{callback_data.stars}:{usd}"
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{callback_data.stars} ⭐", amount=callback_data.stars)],
    )


@stars_router.pre_checkout_query()
async def stars_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@stars_router.message(F.successful_payment)
async def stars_successful_payment(message: Message, session: AsyncSession,
                                   language: Language):
    sp = message.successful_payment
    charge_id = getattr(sp, "telegram_payment_charge_id", None)
    if charge_id:
        existing = await StarsPaymentRepository.get_by_charge_id(charge_id, session)
        if existing is not None:
            logging.info("Duplicate Stars payment webhook ignored for charge_id=%s", charge_id)
            return

    rate = get_rate()
    usd = 0.0
    stars = 0
    tg_id = message.from_user.id
    try:
        _, tg_id_s, stars_s, usd_s = sp.invoice_payload.split(":")
        tg_id = int(tg_id_s)
        stars = int(stars_s)
        usd = round(float(usd_s), 2)
    except Exception as e:
        logging.warning("Failed to parse Stars payload '%s': %s", sp.invoice_payload, e)
        usd = round((sp.total_amount / 1000000) * rate, 2)
    user = await UserRepository.get_by_tgid(tg_id, session)
    if user is None:
        await message.answer(get_text(language, BotEntity.COMMON, "stars_failed"))
        return

    if charge_id:
        await StarsPaymentRepository.create(StarsPaymentDTO(
            telegram_id=tg_id,
            telegram_payment_charge_id=charge_id,
            provider_payment_charge_id=getattr(sp, "provider_payment_charge_id", None),
            stars_amount=stars,
            usd_amount=usd,
            invoice_payload=sp.invoice_payload,
        ), session)

    await ReferralService.apply_deposit_referral(usd, user, session)
    await session_commit(session)
    sym = config.CURRENCY.get_localized_symbol()
    await message.answer(get_text(language, BotEntity.COMMON, "stars_success").format(
        stars=stars, usd=f"{usd}", sym=sym))
    await NotificationService.send_to_admins(
        f"⭐ Stars top-up by tg:{tg_id} · {stars}⭐ → {usd}{sym}", None)