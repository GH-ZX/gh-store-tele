"""Automated Official PDF Receipt Generator & Telegram Dispatcher.

Renders crisp, high-resolution official PDF purchase invoices using Pillow and dispatches
them directly to the customer in Telegram chat via `bot.send_document()`.
"""
import io
import logging
from datetime import datetime, timezone
from typing import Any

from aiogram.types import BufferedInputFile
from PIL import Image, ImageDraw, ImageFont


class PDFReceiptService:
    @staticmethod
    def generate_receipt_bytes(order_id: int, order_data: dict[str, Any]) -> bytes:
        """Render a branded 800x1100 PDF invoice and return raw PDF bytes."""
        width = 800
        height = 1100
        img = Image.new("RGB", (width, height), (248, 250, 252))
        draw = ImageDraw.Draw(img)

        # Header Gradient Banner (Navy to Sky Blue)
        draw.rectangle([(0, 0), (width, 170)], fill=(15, 23, 42))
        draw.rectangle([(0, 160), (width, 170)], fill=(56, 189, 248))

        # Header Typography
        draw.text((width // 2, 60), "GH STORE", fill=(255, 255, 255), anchor="mm")
        draw.text((width // 2, 105), "OFFICIAL PURCHASE INVOICE & RECEIPT", fill=(148, 163, 184), anchor="mm")
        draw.text((width // 2, 132), "bot.gh-store.me · Digital Services & Licenses", fill=(56, 189, 248), anchor="mm")

        # Invoice Meta Card
        draw.rounded_rectangle([(40, 200), (width - 40, 340)], radius=16, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
        draw.text((70, 230), f"INVOICE #: GH-{order_id:06d}", fill=(15, 23, 42))
        date_str = order_data.get("created_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        draw.text((70, 265), f"Date Issued: {date_str}", fill=(100, 116, 139))
        tg_id = order_data.get("telegram_id") or "Verified"
        draw.text((70, 295), f"Customer Telegram ID: {tg_id}", fill=(100, 116, 139))

        draw.text((width - 70, 240), "STATUS: PAID", fill=(16, 185, 129), anchor="ra")
        draw.text((width - 70, 280), "PAYMENT: CONFIRMED", fill=(100, 116, 139), anchor="ra")

        # Table Header
        draw.rounded_rectangle([(40, 365), (width - 40, 415)], radius=10, fill=(241, 245, 249))
        draw.text((65, 385), "ITEM DESCRIPTION", fill=(71, 85, 105))
        draw.text((450, 385), "QTY", fill=(71, 85, 105), anchor="mm")
        draw.text((width - 65, 385), "TOTAL (USD)", fill=(71, 85, 105), anchor="ra")

        # Items Table Rows
        details = order_data.get("details") or []
        y = 440
        total_sell = float(order_data.get("total_sell") or 0.0)
        all_goods = []

        if not details:
            details = [{"name": "Digital License / Service", "quantity": 1, "sell_usd": total_sell}]

        for idx, item in enumerate(details[:4]):
            pname = str(item.get("name") or "Digital Service")[:40]
            qty = int(item.get("quantity") or 1)
            sell = float(item.get("sell_usd") or (total_sell / len(details)))
            goods = item.get("delivery_goods") or []
            if goods:
                all_goods.extend(goods)

            draw.text((65, y), f"{idx + 1}. {pname}", fill=(15, 23, 42))
            draw.text((450, y), str(qty), fill=(15, 23, 42), anchor="mm")
            draw.text((width - 65, y), f"${sell:.2f}", fill=(15, 23, 42), anchor="ra")
            y += 40

        # Total Box
        draw.line([(40, y + 10), (width - 40, y + 10)], fill=(226, 232, 240), width=2)
        y += 35
        draw.text((width - 250, y), "GRAND TOTAL:", fill=(71, 85, 105))
        draw.text((width - 65, y), f"${total_sell:.2f} USD", fill=(2, 132, 199), anchor="ra")

        # Credentials & Activation Goods Box
        y += 60
        draw.rounded_rectangle([(40, y), (width - 40, y + 260)], radius=16, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
        draw.rectangle([(40, y), (width - 40, y + 45)], fill=(248, 250, 252))
        draw.text((65, y + 15), "DELIVERED CREDENTIALS & LICENSE KEYS", fill=(30, 41, 59))

        cred_y = y + 65
        if not all_goods:
            all_goods = order_data.get("goods") or ["Account / Key automated activation delivered successfully."]

        for g in all_goods[:4]:
            draw.rounded_rectangle([(65, cred_y), (width - 65, cred_y + 36)], radius=6, fill=(241, 245, 249), outline=(226, 232, 240))
            draw.text((80, cred_y + 10), f"• {str(g)[:75]}", fill=(15, 23, 42))
            cred_y += 46

        # Guarantee Badge & Footer
        foot_y = height - 120
        draw.rounded_rectangle([(40, foot_y), (width - 40, foot_y + 55)], radius=10, fill=(236, 253, 245), outline=(167, 243, 208))
        draw.text((width // 2, foot_y + 20), "GUARANTEE: 30-Day Full Replacement Protection Included", fill=(5, 150, 105), anchor="mm")
        draw.text((width // 2, foot_y + 40), "Official GH Store verified order. For support, contact @GHStoreSupport", fill=(100, 116, 139), anchor="mm")

        buf = io.BytesIO()
        img.save(buf, format="PDF", resolution=150.0)
        return buf.getvalue()

    @staticmethod
    def generate_recharge_receipt_bytes(recharge_id: Any, recharge_data: dict[str, Any]) -> bytes:
        """Render an official 800x1100 PDF top-up receipt for completed customer balance deposits."""
        width = 800
        height = 1100
        img = Image.new("RGB", (width, height), (248, 250, 252))
        draw = ImageDraw.Draw(img)

        # Header Gradient Banner (Emerald Green to Teal for Top-ups)
        draw.rectangle([(0, 0), (width, 170)], fill=(6, 78, 59))
        draw.rectangle([(0, 160), (width, 170)], fill=(16, 185, 129))

        draw.text((width // 2, 60), "GH STORE", fill=(255, 255, 255), anchor="mm")
        draw.text((width // 2, 105), "OFFICIAL BALANCE TOP-UP RECEIPT", fill=(167, 243, 208), anchor="mm")
        draw.text((width // 2, 132), "bot.gh-store.me · Wallet Liquidity & Deposit Confirmation", fill=(52, 211, 153), anchor="mm")

        # Invoice Meta Card
        draw.rounded_rectangle([(40, 200), (width - 40, 340)], radius=16, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
        rec_id_str = str(recharge_id).replace("SAM-", "").replace("STR-", "").replace("CRY-", "")
        draw.text((70, 230), f"RECEIPT #: GH-TOPUP-{rec_id_str}", fill=(15, 23, 42))
        date_str = recharge_data.get("created_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        draw.text((70, 265), f"Date Credited: {date_str}", fill=(100, 116, 139))
        tg_id = recharge_data.get("telegram_id") or "Verified Customer"
        draw.text((70, 295), f"Customer Telegram ID: {tg_id}", fill=(100, 116, 139))

        draw.text((width - 70, 240), "STATUS: CREDITED", fill=(16, 185, 129), anchor="ra")
        draw.text((width - 70, 280), "BALANCE: UPDATED", fill=(100, 116, 139), anchor="ra")

        # Deposit Summary Box
        draw.rounded_rectangle([(40, 365), (width - 40, 420)], radius=10, fill=(241, 245, 249))
        draw.text((65, 392), "DEPOSIT CHANNEL & PAYMENT RAIL", fill=(71, 85, 105))
        draw.text((width - 65, 392), "CREDITED AMOUNT", fill=(71, 85, 105), anchor="ra")

        y = 445
        method = str(recharge_data.get("method") or "Wallet Top-up").title()
        amt_usd = float(recharge_data.get("amount_usd") or 0.0)
        draw.text((65, y), f"• {method}", fill=(15, 23, 42))
        draw.text((width - 65, y), f"+${amt_usd:.2f} USD", fill=(16, 185, 129), anchor="ra")

        loc_amt = recharge_data.get("invoice_amount")
        if loc_amt and recharge_data.get("currency") == "SYP":
            y += 35
            draw.text((65, y), "  (Equivalent Local Currency Settlement)", fill=(100, 116, 139))
            draw.text((width - 65, y), f"≈ {int(loc_amt):,} SYP", fill=(100, 116, 139), anchor="ra")

        # Verification & Audit Details
        y += 50
        draw.line([(40, y), (width - 40, y)], fill=(226, 232, 240), width=2)
        y += 25

        draw.rounded_rectangle([(40, y), (width - 40, y + 250)], radius=16, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
        draw.rectangle([(40, y), (width - 40, y + 45)], fill=(248, 250, 252))
        draw.text((65, y + 15), "TRANSACTION AUDIT & SETTLEMENT DETAILS", fill=(30, 41, 59))

        box_y = y + 65
        inv_id = recharge_data.get("invoice_id") or "Direct Deposit"
        draw.text((70, box_y), f"• Reference / Txn ID: {inv_id}", fill=(15, 23, 42))
        box_y += 38

        is_admin_approved = bool(recharge_data.get("approved_by_admin"))
        approval_text = "Verified & Approved by Store Administration" if is_admin_approved else "Verified by Automated Payment Gateway"
        draw.text((70, box_y), f"• Confirmation Mode: {approval_text}", fill=(5, 150, 105))
        box_y += 38

        draw.text((70, box_y), "• Destination: Customer Spendable Bot Balance", fill=(100, 116, 139))
        box_y += 38

        draw.text((70, box_y), "• Usable for all digital products, keys, and subscriptions instantly.", fill=(100, 116, 139))

        # Footer
        foot_y = height - 120
        draw.rounded_rectangle([(40, foot_y), (width - 40, foot_y + 55)], radius=10, fill=(236, 253, 245), outline=(167, 243, 208))
        draw.text((width // 2, foot_y + 20), "OFFICIAL GH STORE DEPOSIT VOUCHER", fill=(5, 150, 105), anchor="mm")
        draw.text((width // 2, foot_y + 40), "Funds are secured and ready for immediate in-store checkout. @GHStoreSupport", fill=(100, 116, 139), anchor="mm")

        buf = io.BytesIO()
        img.save(buf, format="PDF", resolution=150.0)
        return buf.getvalue()

    @staticmethod
    async def dispatch_pdf_receipt(order_id: int, telegram_id: int, order_data: dict[str, Any], bot) -> bool:
        """Generate PDF invoice and dispatch to customer via Telegram bot.send_document."""
        if not bot or not telegram_id:
            return False
        try:
            pdf_bytes = PDFReceiptService.generate_receipt_bytes(order_id, order_data)
            doc = BufferedInputFile(pdf_bytes, filename=f"GHStore_Receipt_#{order_id}.pdf")
            caption = (
                f"🧾 <b>إيصال الشراء الرسمي لطلبك #{order_id}</b>\n\n"
                f"شكراً لتسوقك معنا في GH Store! يمكنك حفظ هذا الإيصال كإثبات شراء رسمي وضمان للمنتج."
            )
            await bot.send_document(chat_id=telegram_id, document=doc, caption=caption, parse_mode="HTML")
            return True
        except Exception as e:
            logging.warning("Could not dispatch PDF receipt to %s: %s", telegram_id, e)
            return False
