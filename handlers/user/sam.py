from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import config
from callbacks import SamCallback, MyProfileCallback
from db import session_commit
from enums.bot_entity import BotEntity
from enums.language import Language
from handlers.user.constants import UserStates
from models.sam_payment import SamPaymentDTO
from repositories.sam_payment import SamPaymentRepository
from repositories.user import UserRepository
from services.sam import SamService
from services.config import ConfigService
from utils.custom_filters import IsUserExistFilter
from utils.utils import get_text

sam_router = Router(name="sam")


async def _provider_enabled(session: AsyncSession, config_key: str, env_value: bool) -> bool:
    raw = await ConfigService.get(session, config_key,
                                  env_fallback="true" if env_value else "false",
                                  default="false")
    return isinstance(raw, str) and raw.strip().lower() in ("1", "true", "yes", "on")


def _back(language: Language) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=MyProfileCallback.create(level=1).pack())


@sam_router.callback_query(SamCallback.filter(F.level == 0), IsUserExistFilter())
async def sam_pick_provider(callback: CallbackQuery, callback_data: SamCallback,
                            session: AsyncSession, language: Language):
    kb_builder = InlineKeyboardBuilder()
    shamcash_enabled = await _provider_enabled(session, "TOPUP_ENABLE_SHAMCASH", config.TOPUP_ENABLE_SHAMCASH)
    syriatel_enabled = await _provider_enabled(session, "TOPUP_ENABLE_SYRIATEL", config.TOPUP_ENABLE_SYRIATEL)
    if shamcash_enabled:
        kb_builder.button(text=get_text(language, BotEntity.COMMON, "sam_provider_shamcash"),
                          callback_data=SamCallback.create(level=1, provider="shamcash").pack())
    if syriatel_enabled:
        kb_builder.button(text=get_text(language, BotEntity.COMMON, "sam_provider_syriatel"),
                          callback_data=SamCallback.create(level=1, provider="syriatel").pack())
    kb_builder.adjust(1)
    kb_builder.row(_back(language))
    if not shamcash_enabled and not syriatel_enabled:
        await callback.answer(get_text(language, BotEntity.COMMON, "sam_pay_failed"))
        return
    await callback.message.edit_caption(
        caption=get_text(language, BotEntity.COMMON, "sam_pick_provider"),
        reply_markup=kb_builder.as_markup())


@sam_router.callback_query(SamCallback.filter(F.level == 1), IsUserExistFilter())
async def sam_amount_prompt(callback: CallbackQuery, callback_data: SamCallback,
                            state: FSMContext, language: Language):
    await state.set_state(UserStates.sam_top_up_amount)
    await state.update_data(sam_provider=callback_data.provider, sam_waiting_amount=True)
    currency = config.SAM_CURRENCY or "USD"
    kb_builder = InlineKeyboardBuilder()
    kb_builder.row(_back(language))
    await callback.message.edit_caption(
        caption=get_text(language, BotEntity.COMMON, "sam_amount_prompt").format(currency=currency),
        reply_markup=kb_builder.as_markup())


@sam_router.message(UserStates.sam_top_up_amount, F.text, IsUserExistFilter())
async def sam_amount_received(message: Message, session: AsyncSession,
                              state: FSMContext, language: Language):
    state_data = await state.get_data()
    if not state_data.get("sam_waiting_amount"):
        return
    raw = (message.text or "").strip()
    try:
        amount = float(raw)
        valid = 1 <= amount < 1000000
    except ValueError:
        valid = False
    if not valid:
        currency = config.SAM_CURRENCY or "USD"
        await message.answer(get_text(language, BotEntity.COMMON, "sam_invalid_amount").format(currency=currency))
        return

    provider = state_data.get("sam_provider")
    currency = config.SAM_CURRENCY or "USD"
    user = await UserRepository.get_by_tgid(message.from_user.id, session)
    identifier = await ConfigService.get(session, "SAM_RECEIVING_WALLET",
                                         env_fallback=config.SAM_RECEIVING_WALLET)
    try:
        invoice = await SamService.create_invoice(
            session, provider, identifier, amount, currency,
            webhook_url=f"https://{(config.BATSTORE_WEBHOOK_URL or 'localhost').removesuffix('/ventebot')}/samwebhook"
        )
    except Exception as e:
        import logging
        logging.error("SAM invoice creation failed: %s", e)
        await message.answer(get_text(language, BotEntity.COMMON, "sam_pay_failed"))
        await state.set_state()
        await state.update_data(sam_waiting_amount=False)
        return

    invoice_id = invoice.get("invoiceId")
    payment_url = invoice.get("paymentUrl")
    usd_amount = amount
    if currency.upper() == "SYP":
        try:
            usd_amount = round(amount * float(config.SAM_SYP_USD_RATE or "0.002551"), 2)
        except ValueError:
            usd_amount = round(amount * 0.002551, 2)

    if invoice_id:
        await SamPaymentRepository.create(SamPaymentDTO(
            invoice_id=invoice_id,
            telegram_id=message.from_user.id,
            method=provider,
            currency=currency,
            amount=amount,
            usd_amount=usd_amount,
            payment_url=payment_url,
            event="pending",
        ), session)
        await session_commit(session)

    await state.set_state()
    await state.update_data(sam_waiting_amount=False)

    kb_builder = InlineKeyboardBuilder()
    if payment_url:
        kb_builder.button(text="💳 Open payment page", url=payment_url)
    kb_builder.row(_back(language))
    await message.answer(
        get_text(language, BotEntity.COMMON, "sam_invoice_created").format(url=payment_url or "N/A"),
        reply_markup=kb_builder.as_markup())