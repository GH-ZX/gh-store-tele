import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import config
from callbacks import AllCategoriesCallback
from enums.bot_entity import BotEntity
from enums.language import Language
from handlers.user.constants import UserStates
from models.batstore_product import format_product_icon
from repositories.batstore_product import BatStoreProductRepository
from services.restock_notification import RestockNotificationService
from utils.custom_filters import IsUserExistFilter
from utils.utils import get_text

search_router = Router(name="search")


def _build_search_kb(results, language: Language) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    sym = config.CURRENCY.get_localized_symbol()
    for p in results:
        is_oos = RestockNotificationService.is_batstore_out_of_stock(p)
        icon = p.emoji or "⚡"
        label = f"{icon} {p.name}"
        if p.sell_price_usd is not None:
            label = f"{label} — {p.sell_price_usd:.2f}{sym}"
        if is_oos:
            label = f"🔴 {label}"
        kb.button(
            text=label,
            callback_data=AllCategoriesCallback.create(
                level=2,
                batstore_product_id=p.product_id,
                batstore_category_name=p.category or "Other",
            ).pack(),
        )
    kb.adjust(1)
    kb.row(
        InlineKeyboardButton(
            text=get_text(language, BotEntity.COMMON, "back_button"),
            callback_data=AllCategoriesCallback.create(level=0).pack(),
        )
    )
    return kb


@search_router.message(Command("search"), IsUserExistFilter())
async def search_command(message: Message, command: CommandObject,
                         session: AsyncSession, state: FSMContext,
                         language: Language):
    query = (command.args or "").strip()
    if not query:
        await state.set_state(UserStates.search_query)
        prompt = (
            "🔍 <b>Search Digital Products & Services</b>\n\n"
            "Please send the product name or keyword you are looking for\n"
            "(e.g. <code>ChatGPT</code>, <code>Gemini</code>, <code>Claude</code>, <code>Netflix</code>, <code>VPN</code>):"
        )
        await message.answer(prompt)
        return

    await execute_search(message, query, session, language)


@search_router.message(UserStates.search_query, F.text, IsUserExistFilter())
async def search_query_received(message: Message, session: AsyncSession,
                                state: FSMContext, language: Language):
    query = (message.text or "").strip()
    await state.clear()
    await execute_search(message, query, session, language)


async def execute_search(message: Message, query: str,
                         session: AsyncSession, language: Language):
    results = await BatStoreProductRepository.search(query, session, limit=12)
    if not results:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(
                text=get_text(language, BotEntity.COMMON, "back_button"),
                callback_data=AllCategoriesCallback.create(level=0).pack(),
            )
        )
        await message.answer(
            f"🔍 <b>No products found for:</b> \"<i>{query}</i>\"\n\n"
            "Try a different keyword or browse all categories.",
            reply_markup=kb.as_markup()
        )
        return

    kb = _build_search_kb(results, language)
    await message.answer(
        f"🔍 <b>Search Results for:</b> \"<i>{query}</i>\" ({len(results)} found)\n\n"
        "Tap a product below to view details and purchase:",
        reply_markup=kb.as_markup()
    )


@search_router.inline_query()
async def inline_search(inline_query: InlineQuery, session: AsyncSession):
    query = (inline_query.query or "").strip()
    if not query:
        products = await BatStoreProductRepository.get_visible(session)
        products = products[:10]
    else:
        products = await BatStoreProductRepository.search(query, session, limit=10)

    sym = config.CURRENCY.get_localized_symbol()
    articles = []
    for p in products:
        icon = p.emoji or "⚡"
        price_str = f"{p.sell_price_usd:.2f}{sym}" if p.sell_price_usd else "N/A"
        desc = p.description or f"{p.category or 'Digital Good'} · Instant Delivery"
        content = (
            f"<b>{icon} {p.name}</b>\n\n"
            f"{desc}\n\n"
            f"💲 Price: <b>{price_str}</b>\n"
            f"📦 Category: {p.category or 'Other'}\n\n"
            "<i>Open the bot to purchase with your balance!</i>"
        )
        articles.append(
            InlineQueryResultArticle(
                id=str(p.product_id),
                title=f"{icon} {p.name} — {price_str}",
                description=desc[:100],
                input_message_content=InputTextMessageContent(
                    message_text=content,
                    parse_mode="HTML",
                ),
            )
        )

    await inline_query.answer(articles, cache_time=300, is_personal=True)
