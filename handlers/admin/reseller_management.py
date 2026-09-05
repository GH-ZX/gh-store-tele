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
    kb.button(text="🎨 Custom Emojis", callback_data=ResellerManagementCallback.create(level=1, action="custom_emojis").pack())
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
            raw_bal = me_data.get("wallet_balance")
            if raw_bal is None:
                raw_bal = me_data.get("wallet", {}).get("balance", "0.00")
            try:
                balance = f"{float(raw_bal):.2f}"
            except (ValueError, TypeError):
                balance = str(raw_bal)
            username = me_data.get("username") or me_data.get("user", {}).get("username", "N/A")
            tier = me_data.get("key_name") or me_data.get("user", {}).get("tier", "Standard")
            text = (
                "💰 <b>Reseller API Wallet Balance</b>\n\n"
                f"• <b>Account:</b> {username}\n"
                f"• <b>Key / Tier:</b> {tier}\n"
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

    elif action == "custom_emojis":
        from services.custom_emoji import CustomEmojiService
        rules = await CustomEmojiService.get_rules(session)
        lines = ["🎨 <b>Telegram Custom Animated Emoji Rules</b>\n"]
        lines.append("Products with matching keywords automatically get these animated icons:\n")
        # Show top 12 rules
        for kw, rule in list(rules.items())[:14]:
            em = rule.get("emoji") or "⚡"
            cid = rule.get("custom_emoji_id")
            if cid:
                lines.append(f"• <b>{kw}:</b> <tg-emoji emoji-id=\"{cid}\">{em}</tg-emoji> <code>{cid}</code>")
            else:
                lines.append(f"• <b>{kw}:</b> {em} <i>(standard emoji)</i>")
        if len(rules) > 14:
            lines.append(f"\n<i>...and {len(rules) - 14} more rules configured.</i>")
        lines.append("\n<i>💡 To add or update an animated icon, tap below or send <code>/set_emoji keyword</code>.</i>")

        kb = InlineKeyboardBuilder()
        kb.button(text="➕ Add / Change Keyword Emoji", callback_data=ResellerManagementCallback.create(level=1, action="new_emoji_rule").pack())
        kb.row(_reseller_back_button(language))
        await callback.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())

    elif action == "new_emoji_rule":
        await state.set_state(ResellerManagementStates.set_custom_emoji_keyword)
        text = (
            "✏️ <b>Enter Product Keyword</b>\n\n"
            "Send the keyword or service name that should use this icon\n"
            "(e.g. <code>claude</code>, <code>gemini</code>, <code>netflix</code>, <code>chatgpt</code>, <code>vpn</code>):"
        )
        kb = InlineKeyboardBuilder()
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


@reseller_management_router.message(AdminIdFilter(), F.text.startswith("/set_emoji"))
async def set_emoji_command(message: Message, state: FSMContext, session: AsyncSession, language: Language):
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip():
        kw = parts[1].strip().lower()
        await state.update_data(target_keyword=kw)
        await state.set_state(ResellerManagementStates.set_custom_emoji_icon)
        await message.answer(
            f"🎨 <b>Assigning icon for keyword:</b> <code>{kw}</code>\n\n"
            "Now please send the <b>custom animated emoji</b> from your Telegram Premium picker (or any standard emoji):"
        )
    else:
        await state.set_state(ResellerManagementStates.set_custom_emoji_keyword)
        await message.answer(
            "✏️ <b>Enter Product Keyword</b>\n\n"
            "Please send the keyword or brand name (e.g. <code>claude</code>, <code>gemini</code>, <code>chatgpt</code>):"
        )


@reseller_management_router.message(AdminIdFilter(), ResellerManagementStates.set_custom_emoji_keyword, F.text)
async def receive_emoji_keyword(message: Message, state: FSMContext, language: Language):
    kw = (message.text or "").strip().lower()
    if not kw or len(kw) > 64:
        await message.answer("❌ Invalid keyword. Please send a single word or short phrase:")
        return
    await state.update_data(target_keyword=kw)
    await state.set_state(ResellerManagementStates.set_custom_emoji_icon)
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Cancel", callback_data=ResellerManagementCallback.create(level=0).pack())
    await message.answer(
        f"🎨 <b>Target Keyword:</b> <code>{kw}</code>\n\n"
        "Now send the <b>custom animated emoji</b> from your Telegram Premium picker to attach to this keyword:",
        reply_markup=kb.as_markup()
    )


@reseller_management_router.message(AdminIdFilter(), ResellerManagementStates.set_custom_emoji_icon)
async def receive_emoji_icon(message: Message, state: FSMContext, session: AsyncSession, language: Language):
    from services.custom_emoji import CustomEmojiService
    extracted = CustomEmojiService.extract_from_message(message)
    if not extracted:
        await message.answer("❌ Please send an emoji (standard or custom animated emoji from Telegram Premium):")
        return

    emoji_char, custom_id = extracted
    state_data = await state.get_data()
    kw = state_data.get("target_keyword", "product")
    await state.clear()

    count = await CustomEmojiService.set_rule(kw, emoji_char, custom_id, session)

    preview_tag = f'<tg-emoji emoji-id="{custom_id}">{emoji_char}</tg-emoji>' if custom_id else emoji_char
    reply_text = (
        f"✅ <b>Custom Emoji Saved for keyword:</b> <code>{kw}</code>!\n\n"
        f"• <b>Icon:</b> {emoji_char}\n"
        f"• <b>Custom Emoji ID:</b> <code>{custom_id or 'None (Standard Emoji)'}</code>\n"
        f"• <b>Preview:</b> {preview_tag}\n"
        f"• <b>Catalog Updated:</b> {count} matching products updated immediately!\n\n"
        "<i>Future catalog syncs will automatically apply this icon to products containing this keyword.</i>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⚡ Return to Reseller Menu", callback_data=ResellerManagementCallback.create(level=0).pack())
    kb.row(_back_button(language))
    await message.answer(reply_text, reply_markup=kb.as_markup())


@reseller_management_router.message(AdminIdFilter(), F.entities)
async def inspect_admin_custom_emoji(message: Message, state: FSMContext, language: Language):
    """When an admin casually sends a custom emoji, detect it and offer a 1-tap link to a keyword."""
    current_state = await state.get_state()
    if current_state:
        return  # let active FSM handlers process it

    from services.custom_emoji import CustomEmojiService
    extracted = CustomEmojiService.extract_from_message(message)
    if not extracted or not extracted[1]:
        return

    emoji_char, custom_id = extracted
    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 Link to Keyword", callback_data=ResellerManagementCallback.create(level=1, action="new_emoji_rule").pack())
    kb.row(_back_button(language))
    await message.answer(
        f"✨ <b>Telegram Custom Emoji Detected!</b>\n\n"
        f"• <b>Fallback:</b> {emoji_char}\n"
        f"• <b>Custom Emoji ID:</b> <code>{custom_id}</code>\n"
        f"• <b>Preview:</b> <tg-emoji emoji-id=\"{custom_id}\">{emoji_char}</tg-emoji>\n\n"
        f"<i>To link this icon to a product name keyword, tap below or type <code>/set_emoji &lt;keyword&gt;</code>!</i>",
        reply_markup=kb.as_markup()
    )


@reseller_management_router.callback_query(AdminIdFilter(), F.data.startswith("fulfill_recharge:"))
async def handle_fulfill_recharge_cb(callback: CallbackQuery, session: AsyncSession):
    """Admin fulfilled supplier balance; place order upstream and deliver goods automatically."""
    order_id = int(callback.data.split(":")[1])
    await callback.answer("⏳ جاري تنفيذ الطلب مع المورد...", show_alert=False)
    from services.supplier_recharge import SupplierRechargeService
    success, msg, goods = await SupplierRechargeService.check_and_fulfill_order(order_id, session)
    if success:
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n✅ <b>تم شحن رصيد المورد وتنفيذ وتسليم الطلب #{order_id} للعميل بنجاح! 🎉</b>"
        )
    else:
        await callback.answer(f"⚠️ {msg}", show_alert=True)


@reseller_management_router.callback_query(AdminIdFilter(), F.data.startswith("refund_recharge:"))
async def handle_refund_recharge_cb(callback: CallbackQuery, session: AsyncSession):
    """Admin refunds customer if supplier balance cannot be replenished."""
    order_id = int(callback.data.split(":")[1])
    from repositories.batstore_order import BatStoreOrderRepository
    from repositories.user import UserRepository
    order = await BatStoreOrderRepository.get_by_id(order_id, session)
    if not order or order.status == "refunded":
        await callback.answer("الطلب مسترد مسبقاً أو غير موجود.", show_alert=True)
        return
    user = await UserRepository.get_by_tgid(order.telegram_id, session)
    if user:
        user.top_up_amount = (user.top_up_amount or 0.0) + (order.total_sell or 0.0)
        await UserRepository.update(user, session)
    order.status = "refunded"
    await BatStoreOrderRepository.update(order, session)
    await session_commit(session)
    await callback.message.edit_text(
        f"{callback.message.html_text}\n\n↩️ <b>تم استرداد مبلغ ${order.total_sell:.2f} إلى رصيد العميل بنجاح.</b>"
    )
