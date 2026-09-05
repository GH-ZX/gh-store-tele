import asyncio
import datetime
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from db import get_db_session, session_execute
from models.batstore_order import BatStoreOrder
from models.deposit import Deposit
from models.sam_payment import SamPayment
from models.stars_payment import StarsPayment
from models.user import User
from services.notification import NotificationService


class FinancialDigestService:

    @staticmethod
    async def generate_digest(session: AsyncSession | Session, hours: int = 24) -> str:
        """Calculate P&L and deposit breakdown for the last N hours."""
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
        sym = config.CURRENCY.get_localized_symbol()

        # 1. Crypto deposits
        stmt_crypto = (
            select(func.coalesce(func.sum(Deposit.fiat_amount), 0.0), func.count(Deposit.id))
            .where(Deposit.deposit_datetime >= since)
        )
        res_crypto = await session_execute(stmt_crypto, session)
        crypto_total, crypto_count = res_crypto.first() or (0.0, 0)

        # 2. Stars deposits
        stmt_stars = (
            select(func.coalesce(func.sum(StarsPayment.usd_amount), 0.0), func.count(StarsPayment.id))
            .where(StarsPayment.created_at >= since)
        )
        res_stars = await session_execute(stmt_stars, session)
        stars_total, stars_count = res_stars.first() or (0.0, 0)

        # 3. SAM deposits
        stmt_sam = (
            select(func.coalesce(func.sum(SamPayment.usd_amount), 0.0), func.count(SamPayment.id))
            .where(SamPayment.created_at >= since, SamPayment.event == "invoice.paid")
        )
        res_sam = await session_execute(stmt_sam, session)
        sam_total, sam_count = res_sam.first() or (0.0, 0)

        total_inflow = float(crypto_total) + float(stars_total) + float(sam_total)

        # 4. Sales & Fulfillment (completed BatStore orders only)
        stmt_orders = (
            select(BatStoreOrder)
            .where(BatStoreOrder.created_at >= since, BatStoreOrder.status == "completed")
        )
        res_orders = await session_execute(stmt_orders, session)
        orders = list(res_orders.scalars().all())

        total_sales = 0.0
        wholesale_cost = 0.0
        for o in orders:
            total_sales += o.total_sell or 0.0
            for d in (o.details or []):
                wholesale_cost += (d.get("cost_usd") or 0.0) * (d.get("quantity") or 1)

        gross_profit = total_sales - wholesale_cost
        margin_pct = (gross_profit / wholesale_cost * 100) if wholesale_cost > 0 else 0.0

        # 5. New user signups
        stmt_users = (
            select(func.count(User.id))
            .where(User.registered_at >= since)
        )
        res_users = await session_execute(stmt_users, session)
        new_users = res_users.scalar() or 0

        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        return (
            f"📊 <b>GH Store Financial Digest ({hours}h)</b>\n"
            f"<i>Generated: {date_str}</i>\n\n"
            "💰 <b>Customer Inflow (Deposits):</b>\n"
            f"• Crypto: {crypto_total:.2f}{sym} ({crypto_count} tx)\n"
            f"• Telegram Stars: {stars_total:.2f}{sym} ({stars_count} tx)\n"
            f"• SAM Cash: {sam_total:.2f}{sym} ({sam_count} tx)\n"
            f"• <b>Total Top-ups:</b> <b>{total_inflow:.2f}{sym}</b>\n\n"
            "🛒 <b>Sales & Fulfillment:</b>\n"
            f"• Orders: {len(orders)} fulfilled\n"
            f"• Customer Revenue: {total_sales:.2f}{sym}\n"
            f"• Wholesale Cost: {wholesale_cost:.2f}{sym}\n"
            f"• <b>Gross Profit (before fees):</b> <b>{'+' if gross_profit >= 0 else ''}{gross_profit:.2f}{sym}</b> ({margin_pct:.1f}%)\n\n"
            f"👥 <b>New Customers:</b> {new_users} registrations"
        )

    @staticmethod
    async def send_daily_digest() -> None:
        """Fetch stats and dispatch to all configured admins."""
        try:
            async with get_db_session() as session:
                report = await FinancialDigestService.generate_digest(session, hours=24)
            await NotificationService.send_to_admins(report, None)
            logging.info("Daily financial digest sent to admins.")
        except Exception as e:
            logging.error("Failed to generate daily financial digest: %s", e)


async def daily_digest_cron():
    """Background task dispatching a 24-hour financial report once daily."""
    while True:
        await asyncio.sleep(86400)  # every 24 hours
        await FinancialDigestService.send_daily_digest()
