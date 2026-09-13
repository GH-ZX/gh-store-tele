"""Supplier Balance Recharge & On-Demand Order Fulfillment Engine.

When an upstream provider lacks balance to fulfill wholesale costs, this engine
queues the order in `pending_supplier_recharge`, notifies the customer of in-progress
status, alerts admins with 1-tap fulfillment buttons, and automatically delivers credentials
once the provider balance is replenished.
"""
import logging
from typing import Any

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

import config
from db import session_commit
from models.batstore_order import BatStoreOrder
from models.batstore_product import BatStoreProduct
from models.user import User
from repositories.batstore_order import BatStoreOrderRepository
from repositories.batstore_product import BatStoreProductRepository
from repositories.user import UserRepository
from services.batstore import BatStoreService
from services.notification import NotificationService
from services.prodseller import ProdSellerService


class SupplierRechargeService:
    @staticmethod
    async def notify_customer_order_queued(order_id: int, product_name: str, telegram_id: int) -> None:
        """Inform customer their payment is confirmed and their order is being activated."""
        from bot import bot
        try:
            msg = (
                f"⏳ <b>تم استلام وتأكيد طلبك #{order_id} بنجاح!</b>\n\n"
                f"• <b>المنتج:</b> {product_name}\n"
                f"• <b>الحالة:</b> قيد التجهيز والتفعيل التلقائي من قبل الإدارة.\n\n"
                f"سيصلك إشعار فوري يحتوي على بيانات الحساب / كود التفعيل هنا فور اكتمال التجهيز! ✨"
            )
            await bot.send_message(chat_id=telegram_id, text=msg, parse_mode="HTML")
        except Exception as e:
            logging.warning("Could not send order queued notification to %s: %s", telegram_id, e)

    @staticmethod
    async def notify_admin_recharge_needed(
        order: BatStoreOrder,
        product: BatStoreProduct,
        quantity: int,
        wholesale_cost: float,
        user: User | None = None,
    ) -> None:
        """Send admin an alert card with 1-tap fulfillment and refund inline buttons."""
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"⚡ تم الشحن - تنفيذ وتسليم طلب #{order.id}",
                callback_data=f"fulfill_recharge:{order.id}"
            )],
            [InlineKeyboardButton(
                text="↩️ استرداد رصيد العميل",
                callback_data=f"refund_recharge:{order.id}"
            )]
        ])
        user_info = f"tg:{order.telegram_id}"
        if user and user.telegram_username:
            user_info = f"@{user.telegram_username} (<code>{order.telegram_id}</code>)"

        supplier_name = getattr(product, "supplier", "batstore").upper()
        msg = (
            f"⚠️ <b>طلب جديد بحاجة لشحن رصيد المورد!</b>\n\n"
            f"• <b>رقم الطلب:</b> #{order.id}\n"
            f"• <b>العميل:</b> {user_info}\n"
            f"• <b>المنتج:</b> {product.name} ({quantity}×)\n"
            f"• <b>المورد المستهدف:</b> {supplier_name}\n"
            f"• <b>المطلوب شحنه (Wholesale):</b> <b>${wholesale_cost:.2f} USD</b>\n"
            f"• <b>المبلغ المدفوع من العميل:</b> ${float(order.total_sell or 0.0):.2f} USD (تم خصمه)\n\n"
            f"<i>يرجى شحن حساب المورد ثم النقر على الزر أدناه لتنفيذ الطلب وتسليمه تلقائياً للعميل.</i>"
        )
        await NotificationService.send_to_admins(msg, reply_markup=kb)

    @staticmethod
    async def check_and_fulfill_order(order_id: int, session: AsyncSession) -> tuple[bool, str, list]:
        """Resume only unsubmitted items using their original persisted keys."""
        from services.order_fulfillment import FulfillmentService
        from services.order_polling import _notify_order_complete
        order = await FulfillmentService.fulfill_order(order_id, session)
        await session.commit()
        if order is None:
            return False, "Order not found", []
        goods = [good for item in order.details or [] for good in item.get("delivery_goods", [])]
        if order.status == "completed":
            await _notify_order_complete(order, goods)
            return True, "Order completed", goods
        return False, f"Order status: {order.status}. Pending or uncertain purchases are reconciled before retrying.", goods
