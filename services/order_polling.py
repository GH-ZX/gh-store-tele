import asyncio
import logging

import config
from db import get_db_session, session_commit, session_execute
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
                await drain_retry_order_queue(session)
                pending = await BatStoreOrderRepository.get_pending(session)

            for order in pending:
                if not order.external_order_ref:
                    continue
                ref_str = str(order.external_order_ref).strip()
                is_numeric = ref_str.isdigit()
                order_id = int(ref_str) if is_numeric else ref_str

                _order_attempts[order.id] += 1
                if _order_attempts[order.id] > _MAX_ATTEMPTS:
                    logging.warning("Order %s exceeded max polling attempts (%s)", order.id, _MAX_ATTEMPTS)
                    async with get_db_session() as session:
                        await BatStoreOrderRepository.update_status(
                            order.id, "requires_manual_review", None, session)
                        await session_commit(session)
                    await NotificationService.send_to_admins(
                        f"⚠️ Order #{order.id} (tg:{order.telegram_id}) exceeded max polling attempts ({_MAX_ATTEMPTS}). "
                        f"Status set to requires_manual_review. Upstream ID: {order.external_order_ref}",
                        None
                    )
                    _order_attempts.pop(order.id, None)
                    continue

                try:
                    if is_numeric:
                        async with get_db_session() as session:
                            order_data = await asyncio.wait_for(
                                BatStoreService.get_order(session, int(order_id)),
                                timeout=15.0
                            )
                        reseller_status = BatStoreService.get_order_reseller_status(order_data)
                        goods = BatStoreService.extract_delivery_goods(order_data)
                    else:
                        from services.prodseller import ProdSellerService
                        async with get_db_session() as session:
                            order_data = await asyncio.wait_for(
                                ProdSellerService.get_order(session, str(order_id)),
                                timeout=15.0
                            )
                        reseller_status = ProdSellerService.get_order_reseller_status(order_data)
                        goods = ProdSellerService.extract_delivery_goods(order_data)
                except asyncio.TimeoutError:
                    logging.warning("Timeout checking order %s after 15s", order.id)
                    continue
                except Exception as e:
                    logging.warning("Failed to check order %s: %s", order.id, e)
                    continue

                if reseller_status == "completed":
                    async with get_db_session() as session:
                        await BatStoreOrderRepository.update_status(
                            order.id, "completed", goods, session)
                        await session_commit(session)
                    _order_attempts.pop(order.id, None)
                    await _notify_order_complete(order, goods)

                elif reseller_status == "failed":
                    async with get_db_session() as session:
                        await BatStoreOrderRepository.update_status(
                            order.id, "failed", None, session)
                        await session_commit(session)
                    _order_attempts.pop(order.id, None)
                    async with get_db_session() as session:
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
        from bot import bot
        from services.pdf_receipt import PDFReceiptService
        date_str = order.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if getattr(order, "created_at", None) else None
        await PDFReceiptService.dispatch_pdf_receipt(
            order_id=order.id,
            telegram_id=order.telegram_id,
            order_data={"details": order.details, "total_sell": order.total_sell, "created_at": date_str, "goods": goods},
            bot=bot
        )
    except Exception as e:
        logging.error("Failed to notify user %s about order %s: %s",
                      order.telegram_id, order.id, e)

async def _refund_and_notify(order, session):
    """Refund customer balance and notify about failed order."""
    from repositories.user import UserRepository
    from services.sale_pricing import externally_paid
    user = await UserRepository.get_by_tgid(order.telegram_id, session)
    if user is None:
        logging.error("Cannot refund order %s: user %s not found", order.id, order.telegram_id)
        return

    refund_amount = order.total_sell or 0.0
    if externally_paid(order):
        logging.info("Order %s was paid externally; marking failed without wallet credit", order.id)
    else:
        await UserRepository.refund_balance(order.telegram_id, refund_amount, session)
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
        if config.BATSTORE_SYNC_ENABLED or getattr(config, "PRODSELLER_SYNC_ENABLED", True):
            try:
                async with get_db_session() as session:
                    from services.multi_supplier import MultiSupplierService
                    res = await MultiSupplierService.sync_all_suppliers(session)
                    await check_warranty_expiries(session)
                    from services.subscription_tracker import SubscriptionTrackerService
                    from repositories.batstore_product import BatStoreProductRepository
                    await SubscriptionTrackerService.check_expiring_subscriptions(session, redis_client=BatStoreProductRepository._redis)
            except Exception as e:
                logging.error("Periodic catalog sync failed: %s", e)

_low_balance_alerted = False


async def check_reseller_balance(session) -> float | None:
    """Check reseller balances across all suppliers (BatStore and ProdSeller), alert once if below threshold."""
    global _low_balance_alerted
    bal_bat = None
    try:
        me_data = await BatStoreService.me(session)
        raw_bal = me_data.get("wallet_balance")
        if raw_bal is None:
            raw_bal = me_data.get("wallet", {}).get("balance", 0.0)
        bal_bat = float(raw_bal)
        if bal_bat < 5.0:
            if not _low_balance_alerted:
                await NotificationService.send_error_to_admins(
                    "low_reseller_balance_batstore",
                    f"⚠️ <b>Low Reseller Balance — سيرفر 1 (BatStore)</b>\n\n"
                    f"• Current Balance: <b>${bal_bat:.2f}</b>\n"
                    f"• Alert Threshold: $5.00\n\n"
                    "<i>Please top up your BatStore reseller wallet.</i>",
                    None,
                    window_seconds=86400,
                )
                _low_balance_alerted = True
        else:
            _low_balance_alerted = False
    except Exception as e:
        logging.debug("Could not check BatStore balance: %s", e)

    try:
        from services.prodseller import ProdSellerService
        ps_data = await ProdSellerService.get_balance(session)
        bal_ps = float(ps_data.get("balance") or 0.0)
        if bal_ps < 5.0:
            await NotificationService.send_error_to_admins(
                "low_reseller_balance_prodseller",
                f"⚠️ <b>Low Reseller Balance — سيرفر 2 (ProdSeller)</b>\n\n"
                f"• Current Balance: <b>${bal_ps:.2f} USDT</b>\n"
                f"• Alert Threshold: $5.00\n\n"
                "<i>Please top up your ProdSeller reseller wallet.</i>",
                None,
                window_seconds=86400,
            )
    except Exception as e:
        logging.debug("Could not check ProdSeller balance: %s", e)

    return bal_bat

async def drain_retry_order_queue(session):
    """Process any queued retry orders from Redis during upstream recovery."""
    from repositories.batstore_product import BatStoreProductRepository
    r = BatStoreProductRepository._redis
    if r is None:
        return
    import json
    for _ in range(5):
        try:
            raw = await r.lpop("ghstore:retry_order_queue")
            if not raw:
                break
            item = json.loads(raw)
            order_id = item["order_id"]
            product_id = item["product_id"]
            quantity = item["quantity"]
            customer_ref = item["customer_reference"]
            placed = await BatStoreService.place_order(
                session, product_id, quantity,
                customer_reference=customer_ref,
                idempotency_key=customer_ref
            )
            ext_ref = placed.get("order", {}).get("id") or placed.get("order_id")
            items = placed.get("order", {}).get("items") or []
            goods_list = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
            order = await BatStoreOrderRepository.get_by_id(order_id, session)
            if order:
                order.external_order_ref = str(ext_ref) if ext_ref else None
                order.status = "completed" if goods_list else "pending_fulfillment"
                await BatStoreOrderRepository.update(order, session)
                await session_commit(session)
                if goods_list:
                    await _notify_order_complete(order, goods_list)
        except Exception as e:
            logging.warning("Failed retry for queued order: %s", e)
            if raw:
                try:
                    await r.rpush("ghstore:retry_order_queue", raw)
                except Exception:
                    pass
            break


async def check_warranty_expiries(session):
    """Check orders nearing warranty expiry (1-3 days remaining) and dispatch a friendly renewal nudge."""
    import datetime
    from repositories.batstore_product import BatStoreProductRepository
    from models.batstore_order import BatStoreOrder
    from sqlalchemy import select
    r = BatStoreProductRepository._redis
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        stmt = (
            select(BatStoreOrder)
            .where(BatStoreOrder.status == "completed")
            .order_by(BatStoreOrder.id.desc())
            .limit(100)
        )
        orders = (await session_execute(stmt, session)).scalars().all()
        for o in orders:
            if not o.created_at or not o.details:
                continue
            warranty_days = 0
            for it in (o.details or []):
                warranty_days = max(warranty_days, int(it.get("warranty_days") or 0))
            if not warranty_days:
                continue
            created_utc = o.created_at.replace(tzinfo=datetime.timezone.utc) if o.created_at.tzinfo is None else o.created_at
            expiry = created_utc + datetime.timedelta(days=warranty_days)
            remaining_secs = (expiry - now).total_seconds()
            if 86400 <= remaining_secs <= 259200:
                nudge_key = f"ghstore:warranty_nudge:{o.id}"
                if r is not None and await r.get(nudge_key):
                    continue
                pname = (o.details[0].get("name") if o.details else "Product") or "المنتج"
                msg = (
                    f"🛡️ <b>تذكير فترة الضمان لطلبك #{o.id}:</b>\n\n"
                    f"باقي <b>3 أيام</b> على انتهاء فترة ضمان منتجك: <b>{pname}</b>.\n"
                    "هل كل شيء يعمل لديك بكفاءة ودون أي مشاكل؟\n"
                    "إذا واجهت أي استفسار أو صعوبة، يرجى التواصل فوراً مع الدعم قبل انتهاء فترة الضمان! ✨"
                )
                try:
                    await NotificationService.send_to_user(msg, o.telegram_id)
                    if r is not None:
                        await r.setex(nudge_key, 2592000, "1")
                except Exception as ex:
                    logging.debug("Failed to send warranty reminder to %s: %s", o.telegram_id, ex)
    except Exception as e:
        logging.warning("Warranty expiry check encountered error: %s", e)


async def periodic_balance_monitor():
    """Periodically check the reseller wallet balance and alert admins once if below $5.00."""
    while True:
        await asyncio.sleep(900)
        try:
            async with get_db_session() as session:
                await check_reseller_balance(session)
        except Exception as e:
            logging.warning("Low balance monitor check failed: %s", e)
