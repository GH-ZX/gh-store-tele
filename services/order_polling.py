import asyncio
import logging

import config
from db import get_db_session, session_commit
from repositories.batstore_order import BatStoreOrderRepository
from services.batstore import BatStoreService
from services.notification import NotificationService
from collections import defaultdict

_POLL_INTERVAL = 60
_MAX_ATTEMPTS = 10
_order_attempts: dict[int, int] = defaultdict(int)

async def poll_pending_orders():
    """Periodically check pending BatStore orders with the reseller API.

    For each pending order:
      - Call GET /orders/{order_id} to check status.
      - If completed: extract goods, update status, notify user.
      - If failed: refund customer balance, update status, notify user.
      - If still pending: leave as-is (will be checked next cycle).
    """
    while True:
        try:
            async with get_db_session() as session:
                pending = await BatStoreOrderRepository.get_pending(session)
                for order in pending:
                    if not order.external_order_ref:
                        continue
                    try:
                        order_id = int(order.external_order_ref)
                        _order_attempts[order.id] += 1
                        if _order_attempts[order.id] > _MAX_ATTEMPTS:
                            logging.warning("Order %s exceeded max polling attempts (%s)", order.id, _MAX_ATTEMPTS)
                            await BatStoreOrderRepository.update_status(
                                order.id, "requires_manual_review", None, session)
                            await session_commit(session)
                            await NotificationService.send_to_admins(
                                f"⚠️ BatStore order #{order.id} (tg:{order.telegram_id}) exceeded max polling attempts ({_MAX_ATTEMPTS}). "
                                f"Status set to requires_manual_review. Upstream ID: {order.external_order_ref}",
                                None
                            )
                            _order_attempts.pop(order.id, None)
                            continue

                        order_data = await asyncio.wait_for(
                            BatStoreService.get_order(session, order_id),
                            timeout=15.0
                        )
                    except asyncio.TimeoutError:
                        logging.warning("Timeout checking order %s after 15s", order.id)
                        continue
                    except Exception as e:
                        logging.warning("Failed to check order %s: %s", order.id, e)
                        continue
                    reseller_status = BatStoreService.get_order_reseller_status(order_data)

                    if reseller_status == "completed":
                        goods = BatStoreService.extract_delivery_goods(order_data)
                        await BatStoreOrderRepository.update_status(
                            order.id, "completed", goods, session)
                        await session_commit(session)
                        _order_attempts.pop(order.id, None)
                        await _notify_order_complete(order, goods)

                    elif reseller_status == "failed":
                        await BatStoreOrderRepository.update_status(
                            order.id, "failed", None, session)
                        await session_commit(session)
                        _order_attempts.pop(order.id, None)
                        await _refund_and_notify(order, session)

        except Exception as e:
            logging.error("poll_pending_orders error: %s", e)

        await asyncio.sleep(_POLL_INTERVAL)


async def _notify_order_complete(order, goods: list[str]):
    """Notify the customer that their order is ready."""
    goods_text = "\n".join(f"• {g}" for g in goods[:20])
    text = (
        f"✅ Your order #{order.id} is ready!\n\n"
        f"📦 Delivered goods:\n{goods_text}"
    )
    try:
        await NotificationService.send_to_user(text, order.telegram_id)
    except Exception as e:
        logging.error("Failed to notify user %s about order %s: %s",
                      order.telegram_id, order.id, e)


async def _refund_and_notify(order, session):
    """Refund customer balance and notify about failed order."""
    from repositories.user import UserRepository
    user = await UserRepository.get_by_tgid(order.telegram_id, session)
    if user is None:
        logging.error("Cannot refund order %s: user %s not found", order.id, order.telegram_id)
        return

    refund_amount = order.total_sell or 0.0
    user.consume_records = max(0, (user.consume_records or 0) - refund_amount)
    await UserRepository.update(user, session)
    await session_commit(session)

    text = (
        f"❌ Your order #{order.id} could not be fulfilled.\n"
        f"💰 {refund_amount:.2f} has been refunded to your balance."
    )
    try:
        await NotificationService.send_to_user(text, order.telegram_id)
    except Exception as e:
        logging.error("Failed to notify user %s about refund for order %s: %s",
                      order.telegram_id, order.id, e)


async def periodic_catalog_sync():
    """Periodically sync the BatStore catalog every hour to keep prices and stock fresh."""
    while True:
        await asyncio.sleep(3600)
        if config.BATSTORE_SYNC_ENABLED:
            try:
                async with get_db_session() as session:
                    created, updated = await BatStoreService.sync_catalog(session)
                logging.info("Periodic catalog sync completed: %s created, %s updated", created, updated)
            except Exception as e:
                logging.error("Periodic catalog sync failed: %s", e)

_low_balance_alerted = False


async def check_reseller_balance(session) -> float | None:
    """Check reseller balance, alert once if below threshold ($5.00), return balance."""
    global _low_balance_alerted
    me_data = await BatStoreService.me(session)
    raw_bal = me_data.get("wallet_balance")
    if raw_bal is None:
        raw_bal = me_data.get("wallet", {}).get("balance", 0.0)
    try:
        bal = float(raw_bal)
        if bal < 5.0:
            if not _low_balance_alerted:
                await NotificationService.send_error_to_admins(
                    "low_reseller_balance",
                    f"⚠️ <b>Low Reseller Wallet Balance!</b>\n\n"
                    f"• Current Balance: <b>${bal:.2f}</b>\n"
                    f"• Alert Threshold: $5.00\n\n"
                    "<i>Please top up your BatStore/VenteBot reseller wallet to prevent customer orders from failing.</i>",
                    None,
                    window_seconds=86400,
                )
                _low_balance_alerted = True
        else:
            # Reset trigger once the account is topped up above $5.00
            _low_balance_alerted = False
        return bal
    except (ValueError, TypeError):
        return None


async def periodic_balance_monitor():
    """Periodically check the reseller wallet balance and alert admins once if below $5.00."""
    while True:
        await asyncio.sleep(900)
        try:
            async with get_db_session() as session:
                await check_reseller_balance(session)
        except Exception as e:
            logging.warning("Low balance monitor check failed: %s", e)
