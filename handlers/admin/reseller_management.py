import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import config
from callbacks import AdminMenuCallback, ResellerManagementCallback
from db import session_commit
from enums.bot_entity import BotEntity
from enums.language import Language
from handlers.admin.constants import ResellerManagementStates
from repositories.batstore_order import BatStoreOrderRepository
from services.batstore import BatStoreService
from services.config import ConfigService
from utils.custom_filters import AdminIdFilter
from utils.utils import get_text

reseller_management_router = Router(name="reseller_management")


def _back_button(language: Language) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=AdminMenuCallback.create(level=0).pack(),
    )


def _reseller_back_button(language: Language) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=ResellerManagementCallback.create(level=0).pack(),
    )


@reseller_management_router.callback_query(AdminIdFilter(), ResellerManagementCallback.filter(F.level == 0))
async def reseller_menu(callback: CallbackQuery,
                        callback_data: ResellerManagementCallback,
                        session: AsyncSession,
                        state: FSMContext,
                        language: Language):
    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Reseller Balance", callback_data=ResellerManagementCallback.create(level=1, action="balance").pack())
    kb.button(text="🔄 Sync Catalog Now", callback_data=ResellerManagementCallback.create(level=1, action="sync").pack())
    kb.button(text="📦 Pending Orders", callback_data=ResellerManagementCallback.create(level=1, action="orders").pack())
    kb.button(text="📊 Set Margin %", callback_data=ResellerManagementCallback.create(level=1, action="set_margin").pack())
    kb.button(text="📈 Financial Digest (24h)", callback_data=ResellerManagementCallback.create(level=1, action="digest").pack())
    kb.adjust(2)
    kb.row(_back_button(language))

    margin_val = await ConfigService.get(session, "MARGIN_PERCENT", env_fallback=config.MARGIN_PERCENT, default="0")
    caption = (
        "⚡ <b>GH Store Reseller & Margins Dashboard</b>\n\n"
        f"• <b>Current Global Margin:</b> {margin_val}%\n"
        f"• <b>BatStore Sync:</b> {'Enabled' if config.BATSTORE_SYNC_ENABLED else 'Disabled'}\n"
        f"• <b>Stars Rail:</b> {'Enabled' if config.GHSTORE_STARS_ENABLED else 'Disabled'}\n\n"
        "Select an administrative action below:"
    )
    if callback.message.caption:
        await callback.message.delete()
        await callback.message.answer(caption, reply_markup=kb.as_markup())
    else:
        await callback.message.edit_text(caption, reply_markup=kb.as_markup())


@reseller_management_router.callback_query(AdminIdFilter(), ResellerManagementCallback.filter(F.level == 1))
async def reseller_action(callback: CallbackQuery,
                          callback_data: ResellerManagementCallback,
                          session: AsyncSession,
                          state: FSMContext,
                          language: Language):
    action = callback_data.action

    if action == "balance":
        try:
            me_data = await BatStoreService.me(session)
            wallet = me_data.get("wallet", {})
            balance = wallet.get("balance", "N/A")
            user_info = me_data.get("user", {})
            username = user_info.get("username", "N/A")
            tier = user_info.get("tier", "standard")
            text = (
                "💰 <b>Reseller API Wallet Balance</b>\n\n"
                f"• <b>Account:</b> {username}\n"
                f"• <b>Tier:</b> {tier}\n"
                f"• <b>USD Balance:</b> ${balance}\n\n"
                "<i>This balance is debited in real time whenever customers buy digital products.</i>"
            )
        except Exception as e:
            text = f"❌ <b>Could not fetch reseller balance:</b>\n<code>{e}</code>"

        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Refresh", callback_data=ResellerManagementCallback.create(level=1, action="balance").pack())
        kb.row(_reseller_back_button(language))
        await callback.message.edit_text(text, reply_markup=kb.as_markup())

    elif action == "sync":
        await callback.message.edit_text("⏳ Syncing products with reseller API, please wait...")
        try:
            created, updated = await BatStoreService.sync_catalog(session)
            text = (
                "✅ <b>BatStore Catalog Synchronized!</b>\n\n"
                f"• <b>New products created:</b> {created}\n"
                f"• <b>Existing products updated:</b> {updated}\n\n"
                "Out-of-stock badges and restock subscriptions have been evaluated."
            )
        except Exception as e:
            text = f"❌ <b>Sync failed:</b>\n<code>{e}</code>"

        kb = InlineKeyboardBuilder()
        kb.row(_reseller_back_button(language))
        await callback.message.edit_text(text, reply_markup=kb.as_markup())

    elif action == "orders":
        orders = await BatStoreOrderRepository.get_pending(session)
        if not orders:
            text = "✅ <b>No pending orders!</b>\n\nAll reseller customer orders are fulfilled or completed."
        else:
            lines = [f"📦 <b>Pending / In-Review Orders ({len(orders)}):</b>\n"]
            for o in orders[:10]:
                ref = o.external_order_ref or "none"
                lines.append(f"• #{o.id} · tg:{o.telegram_id} · ${o.total_sell:.2f} · [{o.status}] · upstream:{ref}")
            if len(orders) > 10:
                lines.append(f"\n<i>...and {len(orders) - 10} more. Manage them in SQLAdmin.</i>")
            text = "\n".join(lines)

        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Refresh", callback_data=ResellerManagementCallback.create(level=1, action="orders").pack())
        kb.row(_reseller_back_button(language))
        await callback.message.edit_text(text, reply_markup=kb.as_markup())

    elif action == "set_margin":
        current_margin = await ConfigService.get(session, "MARGIN_PERCENT", env_fallback=config.MARGIN_PERCENT, default="0")
        await state.set_state(ResellerManagementStates.margin_percent)
        text = (
            "📊 <b>Update Global Margin Percentage</b>\n\n"
            f"Current margin: <b>{current_margin}%</b>\n\n"
            "Please send the new margin percentage as a number (e.g. <code>20</code> for +20%, <code>0</code> for cost price):"
        )
        kb = InlineKeyboardBuilder()
        kb.row(_reseller_back_button(language))
        await callback.message.edit_text(text, reply_markup=kb.as_markup())

    elif action == "digest":
        from services.financial_digest import FinancialDigestService
        text = await FinancialDigestService.generate_digest(session, hours=24)
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Refresh", callback_data=ResellerManagementCallback.create(level=1, action="digest").pack())
        kb.row(_reseller_back_button(language))
        await callback.message.edit_text(text, reply_markup=kb.as_markup())

@reseller_management_router.message(AdminIdFilter(), ResellerManagementStates.margin_percent, F.text)
async def receive_margin_percent(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    raw = (message.text or "").strip().replace("%", "")
    try:
        val = float(raw)
        if val < 0 or val > 1000:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Invalid percentage. Please send a valid number between 0 and 1000:")
        return

    await ConfigService.set(session, "MARGIN_PERCENT", str(val))
    await session_commit(session)
    await state.clear()

    kb = InlineKeyboardBuilder()
    kb.button(text="⚡ Return to Reseller Menu", callback_data=ResellerManagementCallback.create(level=0).pack())
    kb.row(_back_button(language))
    await message.answer(
        f"✅ <b>Global margin updated to {val:g}%!</b>\n\n"
        "New product syncs and catalog displays will automatically calculate sell prices using this margin.",
        reply_markup=kb.as_markup()
    )
