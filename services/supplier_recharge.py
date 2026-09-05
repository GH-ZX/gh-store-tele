"""Supplier Balance Recharge & On-Demand Order Fulfillment Engine.

When an upstream provider lacks balance to fulfill wholesale costs, this engine
queues the order in `pending_supplier_recharge`, notifies the customer of in-progress
status, alerts admins with 1-tap fulfillment buttons, and automatically delivers credentials
once the provider balance is replenished.
"""
import logging
import uuid
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
        """Fulfill a queued order once supplier balance has been topped up.

        Returns (success: bool, message: str, delivered_goods: list).
        """
        from bot import bot
        order = await BatStoreOrderRepository.get_by_id(order_id, session)
        if not order:
            return False, "Order not found", []

        if order.status == "completed":
            return True, "Order already completed", []

        details = order.details or []
        if not details:
            return False, "Missing order product details", []

        all_goods = []
        updated_details = []
        any_failed = False
        error_msg = ""

        for item in details:
            pid = item.get("product_id")
            qty = max(1, int(item.get("quantity") or 1))
            prod = await BatStoreProductRepository.get_by_product_id(pid, session)
            cust_ref = f"fulfill-{order.id}-{uuid.uuid4().hex[:6]}"

            supplier = getattr(prod, "supplier", "batstore") if prod else "batstore"

            try:
                if supplier == "prodseller":
                    placed = await ProdSellerService.place_order(session, pid, qty)
                    items_list = placed.get("order", {}).get("items") or placed.get("items") or []
                    goods = [it.get("value") or it.get("data") or str(it) for it in items_list] if items_list else []
                else:
                    placed = await BatStoreService.place_order(
                        session, pid, qty,
                        customer_reference=cust_ref,
                        idempotency_key=cust_ref,
                    )
                    items_list = placed.get("order", {}).get("items") or placed.get("items") or []
                    goods = [it.get("value") or it.get("data") or str(it) for it in items_list] if items_list else []

                all_goods.extend(goods)
                item["delivery_goods"] = goods
                updated_details.append(item)
            except Exception as e:
                logging.error("Failed to fulfill item #%s during supplier recharge fulfillment: %s", pid, e)
                any_failed = True
                error_msg = str(e)
                updated_details.append(item)

        if any_failed:
            order.details = updated_details
            await BatStoreOrderRepository.update(order, session)
            await session_commit(session)
            return False, f"Supplier placement failed: {error_msg}. Please ensure supplier balance is funded and retry.", all_goods

        order.status = "completed"
        order.details = updated_details
        await BatStoreOrderRepository.update(order, session)
        await session_commit(session)

        # Notify customer in Telegram with delivered credentials
        goods_lines = "\n".join(f"• <code>{g}</code>" for g in all_goods) if all_goods else "تم تفعيل حسابك بنجاح."
        first_name = details[0].get("name") if details else "المنتج"
        try:
            msg = (
                f"🎉 <b>تم اكتمال طلبك #{order.id} وتسليمه بنجاح!</b>\n\n"
                f"• <b>المنتج:</b> {first_name}\n\n"
                f"📦 <b>بيانات التفعيل والتسليم:</b>\n{goods_lines}\n\n"
                f"<i>(انقر على البيانات أعلاه للنسخ المباشر)</i>\n\n"
                f"شكراً لتسوقك مع GH Store! نتمنى لك تجربة ممتعة ✨"
            )
            await bot.send_message(chat_id=order.telegram_id, text=msg, parse_mode="HTML")
        except Exception as e:
            logging.warning("Could not send completed order DM to %s: %s", order.telegram_id, e)
        try:
            from services.pdf_receipt import PDFReceiptService
            date_str = order.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if getattr(order, "created_at", None) else None
            await PDFReceiptService.dispatch_pdf_receipt(
                order_id=order.id,
                telegram_id=order.telegram_id,
                order_data={"details": order.details, "total_sell": order.total_sell, "created_at": date_str, "goods": all_goods},
                bot=bot
            )
        except Exception as e:
            logging.debug("Could not dispatch PDF receipt: %s", e)

        return True, "Order fulfilled and delivered to customer successfully!", all_goods
