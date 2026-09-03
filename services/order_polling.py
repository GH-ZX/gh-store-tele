import asyncio
import logging

from db import get_db_session, session_commit
from repositories.batstore_order import BatStoreOrderRepository
from services.batstore import BatStoreService
from services.notification import NotificationService

_POLL_INTERVAL = 60
_MAX_ATTEMPTS = 10


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
                        order_data = await BatStoreService.get_order(session, order_id)
                    except Exception as e:
                        logging.warning("Failed to check order %s: %s", order.id, e)
                        continue

                    reseller_status = BatStoreService.get_order_reseller_status(order_data)

                    if reseller_status == "completed":
                        goods = BatStoreService.extract_delivery_goods(order_data)
                        await BatStoreOrderRepository.update_status(
                            order.id, "completed", goods, session)
                        await session_commit(session)
                        await _notify_order_complete(order, goods)

                    elif reseller_status == "failed":
                        await BatStoreOrderRepository.update_status(
                            order.id, "failed", None, session)
                        await session_commit(session)
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
