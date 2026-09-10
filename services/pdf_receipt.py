"""Automated Official Purchase Receipt Dispatcher.

Dispatches clean, formatted purchase receipts directly to the customer in Telegram chat.
"""
import logging
from datetime import datetime, timezone
from typing import Any


class ReceiptService:
    @staticmethod
    def generate_receipt_bytes(order_id: int, order_data: dict[str, Any]) -> bytes:
        """Minimal byte representation for backward-compatibility stubs."""
        return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1>>endobj\nxref\n0 3\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n110\n%%EOF"

    @staticmethod
    async def dispatch_receipt(order_id: int, telegram_id: int, order_data: dict[str, Any], bot) -> bool:
        """Dispatch a clean, instant text receipt via Telegram message."""
        if not bot or not telegram_id:
            return False
        try:
            total = float(order_data.get("total_sell") or 0.0)
            date_str = order_data.get("created_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            details = order_data.get("details") or []
            items_lines = []
            for item in details:
                name = item.get("name") or "منتج رقمي"
                qty = item.get("quantity") or 1
                sell = item.get("sell_usd") or total
                items_lines.append(f"• <b>{name}</b> × {qty} — <code>${float(sell):.2f}</code>")
            items_block = "\n".join(items_lines) if items_lines else f"• طلب #{order_id}"

            text = (
                f"🧾 <b>إيصال الشراء الرسمي — GH Store</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📋 <b>رقم الطلب:</b> #{order_id}\n"
                f"📅 <b>التاريخ:</b> {date_str}\n"
                f"💰 <b>المبلغ الإجمالي:</b> <b>${total:.2f} USD</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 <b>المنتجات:</b>\n{items_block}\n\n"
                f"✨ <i>شكراً لتسوقك معنا! بيانات طلبك محفوظة في حسابك.</i>"
            )
            await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
            return True
        except Exception as e:
            logging.debug("Could not dispatch text receipt to %s: %s", telegram_id, e)
            return False

    dispatch_pdf_receipt = dispatch_receipt


PDFReceiptService = ReceiptService
