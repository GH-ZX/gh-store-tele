from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from callbacks import BatStoreCallback
from enums.keyboard_button import KeyboardButton as KB
from enums.language import Language
from services.batstore_store import BatStoreStoreService
from utils.custom_filters import IsUserExistFilter


batstore_router = Router(name="batstore")


@batstore_router.message(Command("batstore"), IsUserExistFilter())
@batstore_router.message(F.text.in_(KB.get_localized_set(KB.BATSTORE)), IsUserExistFilter())
async def batstore_command(message: Message, session: AsyncSession, language: Language):
    caption, kb_builder = await BatStoreStoreService.catalog(message.from_user.id,
                                                             BatStoreCallback.create(level=0),
                                                             session, language)
    await message.answer(caption, reply_markup=kb_builder.as_markup())


@batstore_router.callback_query(BatStoreCallback.filter(F.level == 0), IsUserExistFilter())
async def batstore_catalog(callback: CallbackQuery, callback_data: BatStoreCallback,
                           session: AsyncSession, language: Language):
    caption, kb_builder = await BatStoreStoreService.catalog(callback.from_user.id, callback_data,
                                                             session, language)
    await callback.message.edit_text(text=caption, reply_markup=kb_builder.as_markup())


@batstore_router.callback_query(BatStoreCallback.filter(F.level == 1), IsUserExistFilter())
async def batstore_detail(callback: CallbackQuery, callback_data: BatStoreCallback,
                          state: FSMContext, session: AsyncSession, language: Language):
    caption, kb_builder = await BatStoreStoreService.detail(callback, callback_data, state,
                                                            session, language)
    await callback.message.edit_text(text=caption, reply_markup=kb_builder.as_markup())


@batstore_router.callback_query(BatStoreCallback.filter(F.level == 2), IsUserExistFilter())
async def batstore_confirm(callback: CallbackQuery, callback_data: BatStoreCallback,
                           state: FSMContext, session: AsyncSession, language: Language):
    caption, kb_builder = await BatStoreStoreService.confirm_one(callback, callback_data, state,
                                                                 session, language)
    await callback.message.edit_text(text=caption, reply_markup=kb_builder.as_markup())


@batstore_router.callback_query(BatStoreCallback.filter(F.level == 3), IsUserExistFilter())
async def batstore_checkout(callback: CallbackQuery, callback_data: BatStoreCallback,
                            state: FSMContext, session: AsyncSession, language: Language):
    caption, kb_builder = await BatStoreStoreService.checkout(callback, callback_data, state,
                                                              session, language)
    await callback.message.edit_text(text=caption, reply_markup=kb_builder.as_markup())
