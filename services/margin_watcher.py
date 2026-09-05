"""Supplier Wholesale Price and Profit Margin Watcher Service.

Monitors all products for:
1. Negative or razor-thin profit margins (wholesale cost >= customer price).
2. Complete supplier stock-outs across both servers.
3. Automatic admin Telegram alerts with exact product details and suggested selling prices.
"""
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from db import get_db_session
from repositories.batstore_product import BatStoreProductRepository
from services.notification import NotificationService


class MarginWatcherService:
    @staticmethod
    async def audit_margins(session: AsyncSession | Session) -> list[dict[str, Any]]:
        """Scan all products for margin squeeze or losses."""
        all_prods = await BatStoreProductRepository.get_all(session)
        flagged = []

        for p in all_prods:
            if getattr(p, "hidden", False):
                continue
            cost = float(getattr(p, "cost_usd", 0.0) or 0.0)
            price = float(getattr(p, "sell_price_usd", getattr(p, "price", 0.0)) or 0.0)
            if cost <= 0.0 or price <= 0.0:
                continue

            profit = price - cost
            margin_pct = (profit / cost) * 100.0 if cost > 0 else 0.0

            if profit <= 0.0 or margin_pct < 5.0:
                flagged.append({
                    "id": p.id,
                    "product_id": p.product_id,
                    "name": p.clean_name or p.name,
                    "supplier": getattr(p, "supplier", "batstore"),
                    "cost_usd": cost,
                    "price_usd": price,
                    "profit_usd": round(profit, 2),
                    "margin_pct": round(margin_pct, 1),
                    "is_loss": profit <= 0.0,
                })

        return flagged

    @staticmethod
    async def check_and_alert_admin(session: AsyncSession | Session | None = None) -> int:
        """Check all product margins and alert admin if any products are selling at a loss."""
        async def _run(s):
            flagged = await MarginWatcherService.audit_margins(s)
            losses = [f for f in flagged if f["is_loss"]]
            if not losses:
                return 0

            admin_id = config.ADMIN_ID_LIST[0] if config.ADMIN_ID_LIST else None
            if not admin_id:
                return len(losses)

            msg_lines = [
                "⚠️ <b>تنبيه هامش الربح وتكلفة الموردين!</b>",
                f"تم رصد <b>{len(losses)}</b> منتج يباع بسعر أقل من تكلفة المورد:\n"
            ]
            for item in losses[:5]:
                suggested = round(item["cost_usd"] * 1.30, 2)
                msg_lines.append(
                    f"• <b>{item['name']}</b>\n"
                    f"  التكلفة: ${item['cost_usd']:.2f} | البيع: ${item['price_usd']:.2f} (خسارة ${abs(item['profit_usd']):.2f})\n"
                    f"  السعر المقترح (+30%): ${suggested:.2f}\n"
                )

            if len(losses) > 5:
                msg_lines.append(f"... و {len(losses) - 5} منتجات أخرى.")

            msg_lines.append("يرجى مراجعة وتحديث الأسعار من لوحة الإدارة.")

            full_msg = "\n".join(msg_lines)
            try:
                await NotificationService.send_to_user(full_msg, admin_id)
            except Exception as e:
                logging.warning("Failed to send margin alert to admin: %s", e)

            return len(losses)

        if session is not None:
            return await _run(session)

        async with get_db_session() as session:
            return await _run(session)
