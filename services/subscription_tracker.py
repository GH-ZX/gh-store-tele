"""Automated Subscription Expiration & Renewal Notification Service.

Monitors customer orders for recurring digital subscriptions (e.g. 1 Month / 1 Year
Claude, ChatGPT, Netflix, VPN, Gemini) and proactively alerts users 3 days before expiration
with a direct 1-tap renewal button to maximize Customer Lifetime Value (LTV) and recurring revenue.
"""
import datetime
import logging
import re
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
from db import session_execute
from models.batstore_order import BatStoreOrder
from services.notification import NotificationService
from services.product_spec import ProductSpecParser


class SubscriptionTrackerService:
    @staticmethod
    def parse_duration_days(product_name: str) -> int | None:
        """Extract duration in days from product name."""
        if not product_name:
            return None
        name = product_name.lower()
        if "lifetime" in name or "مدى الحياة" in name:
            return None  # Lifetime licenses don't expire

        # Check explicit day pattern: e.g. "30d", "30 days", "1d"
        m_days = re.search(r"\b(\d+)\s*(days?|d)\b", name)
        if m_days:
            return int(m_days.group(1))

        # Check month pattern: e.g. "1m", "1 month", "3 months", "6 months"
        m_months = re.search(r"\b(\d+)\s*(months?|m)\b", name)
        if m_months:
            months = int(m_months.group(1))
            return months * 30

        # Check year pattern: e.g. "1y", "1 year", "12m"
        m_years = re.search(r"\b(\d+)\s*(years?|yrs?|y)\b", name)
        if m_years:
            years = int(m_years.group(1))
            return years * 365

        # Fallback to ProductSpecParser
        spec = ProductSpecParser.parse(product_name)
        dur_en = spec.get("duration_en") or ""
        if dur_en:
            m = re.search(r"(\d+)\s*(month|year|day)", dur_en, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                unit = m.group(2).lower()
                if unit == "month":
                    return val * 30
                elif unit == "year":
                    return val * 365
                elif unit == "day":
                    return val

        return None

    @staticmethod
    async def check_expiring_subscriptions(session: AsyncSession, redis_client=None, bot=None) -> int:
        """Scan completed orders and send renewal alerts for subscriptions expiring in 1-3 days."""
        now = datetime.datetime.now(datetime.timezone.utc)
        stmt = (
            select(BatStoreOrder)
            .where(BatStoreOrder.status == "completed")
            .order_by(BatStoreOrder.id.desc())
            .limit(200)
        )
        orders = (await session_execute(stmt, session)).scalars().all()
        alerts_sent = 0

        for order in orders:
            if not order.created_at or not order.details:
                continue

            created_utc = order.created_at.replace(tzinfo=datetime.timezone.utc) if order.created_at.tzinfo is None else order.created_at

            for item in order.details:
                pname = item.get("name") or ""
                pid = item.get("product_id")
                duration_days = SubscriptionTrackerService.parse_duration_days(pname)
                if not duration_days or duration_days < 7:
                    continue  # Ignore 1-day/short trial accounts

                expiry_date = created_utc + datetime.timedelta(days=duration_days)
                remaining_seconds = (expiry_date - now).total_seconds()

                # Trigger alert when 1 to 3 days (86400 to 259200 seconds) remain before expiry
                if 86400 <= remaining_seconds <= 259200:
                    alert_key = f"ghstore:sub_renewal_alert:{order.id}:{pid}"
                    if redis_client is not None:
                        try:
                            already_sent = await redis_client.get(alert_key)
                            if already_sent:
                                continue
                        except Exception:
                            pass

                    days_left = max(1, int(round(remaining_seconds / 86400)))
                    bot_username = getattr(config, "BOT_USERNAME", "GHStoreBot") or "GHStoreBot"
                    tma_link = f"https://t.me/{bot_username}/app?startapp=prod_{pid}"

                    msg = (
                        f"⏳ <b>تنبيه موعد تجديد الاشتراك:</b>\n\n"
                        f"عزيزي العميل، اشتراكك لخدمة <b>{pname}</b> في الطلب #{order.id} ينتهي خلال <b>{days_left} أيام</b>!\n\n"
                        f"لتفادي انقطاع الخدمة أو فقدان بياناتك، يمكنك التجديد المباشر الآن بنقرة واحدة:"
                    )
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 تجديد الاشتراك الآن (1-Tap)", url=tma_link)]
                    ])

                    try:
                        await NotificationService.send_to_user(msg, order.telegram_id, reply_markup=kb)
                        alerts_sent += 1
                        if redis_client is not None:
                            try:
                                await redis_client.setex(alert_key, 604800, "1")  # 7 days TTL
                            except Exception:
                                pass
                    except Exception as e:
                        logging.debug("Could not send renewal notification to %s: %s", order.telegram_id, e)

        return alerts_sent
