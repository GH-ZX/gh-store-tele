import asyncio
import logging

import config
from db import get_db_session, session_commit, session_execute
from repositories.batstore_order import BatStoreOrderRepository
from services.batstore import BatStoreService
from services.notification import NotificationService

_POLL_INTERVAL = 60
_MAX_ATTEMPTS = 10

async def poll_one_order(order_id, session):
    from datetime import datetime, timezone
    from services.order_fulfillment import FulfillmentService, normalized_details, locked_order
    order = await locked_order(order_id, session)
    if not order:
        return
    details = normalized_details(order)
    await session.commit()
    # Resume only persisted, demonstrably unsubmitted attempts.
    if any(item.get("status") in {"created", "queued"} for item in details):
        order = await FulfillmentService.fulfill_order(order_id, session)
        details = normalized_details(order)
        await session.commit()
    for index, item in enumerate(details):
        state = item.get("status")
        if state == "submitting":
            try:
                submitted = datetime.fromisoformat(item["submitted_at"])
                stale = (datetime.now(timezone.utc) - submitted).total_seconds() > 300
            except (KeyError, ValueError, TypeError):
                stale = True
            if stale:
                await FulfillmentService.transition_item(order_id, index, "requires_manual_review", None, session)
                await session.commit()
            continue
        if state != "pending_fulfillment":
            continue
        if not item.get("external_order_ref") or not item.get("supplier"):
            await FulfillmentService.transition_item(order_id, index, "requires_manual_review", None, session)
            await session.commit()
            continue
        # Persist polling counters so a restart cannot reset escalation.
        current = await locked_order(order_id, session)
        current_details = normalized_details(current)
        if current_details[index].get("status") != "pending_fulfillment":
            await session.commit()
            continue
        attempts = int(current_details[index].get("poll_attempts") or 0) + 1
        current_details[index]["poll_attempts"] = attempts
        current.details = current_details
        await session.commit()
        if attempts > _MAX_ATTEMPTS:
            await FulfillmentService.transition_item(order_id, index, "requires_manual_review", None, session)
            await session.commit()
            await NotificationService.send_to_admins(f"⚠️ Order #{order_id}, item {index + 1}: supplier reconciliation required.", None)
            continue
        try:
            status, goods = await asyncio.wait_for(FulfillmentService.supplier_status(item, session), timeout=15)
        except Exception as exc:
            logging.warning("Supplier polling failed for order %s item %s: %s", order_id, index, exc)
            await session.rollback()
            continue
        status = str(status).lower()
        if status in {"failed", "refunded", "cancelled", "rejected"}:
            status = "failed"
        elif status in {"completed", "success", "delivered", "active"}:
            status = "completed"
        else:
            await session.commit()
            continue
        updated, changed = await FulfillmentService.transition_item(
            order_id, index, status, goods, session,
            external_ref=item["external_order_ref"], supplier=item["supplier"])
        await session.commit()
        if changed and updated.status == "completed":
            await _notify_order_complete(updated, [
                good for detail in updated.details for good in detail.get("delivery_goods", [])
            ])


async def poll_pending_orders():
    while True:
        try:
            async with get_db_session() as session:
                await drain_retry_order_queue(session)
                pending = await BatStoreOrderRepository.get_pending(session)
                order_ids = [order.id for order in pending]
            for order_id in order_ids:
                try:
                    async with get_db_session() as session:
                        await poll_one_order(order_id, session)
                except Exception:
                    logging.exception("Order polling failed for %s", order_id)
        except Exception:
            logging.exception("poll_pending_orders error")
        await asyncio.sleep(_POLL_INTERVAL)

async def _notify_order_complete(order, goods: list[str]):
    """Notify the customer that their order is ready.

    Sends a full delivery receipt DM: order number, product name, amount
    paid, copyable credentials in <code> tags, a clean step-by-step
    activation guide, and a one-tap WebApp button (startapp=ord_<id>)
    opening the exact order receipt in the Mini App.
    """
    import html
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    details = list(getattr(order, "details", None) or [])
    first = details[0] if details else {}
    if not isinstance(first, dict):
        first, details = {}, []
    raw_product_id = first.get("product_id")
    try:
        product_id = int(raw_product_id) if raw_product_id is not None else None
    except (TypeError, ValueError):
        product_id = None
    product_name = str(first.get("name") or "").strip() or f"Order #{order.id}"
    try:
        amount = float(getattr(order, "total_sell", 0.0) or 0.0)
    except (TypeError, ValueError):
        amount = 0.0

    # Resolve the catalog product for clean activation instructions.
    product = None
    try:
        async with get_db_session() as session:
            from repositories.product import ProductRepository
            if product_id is not None:
                try:
                    product = await ProductRepository.get_by_product_id(product_id, session)
                except Exception:
                    product = None
            if product is None and product_name:
                try:
                    matches = await ProductRepository.search(product_name, session, limit=1)
                    product = matches[0] if matches else None
                except Exception:
                    product = None
    except Exception as e:
        logging.debug("Could not resolve product for order %s: %s", order.id, e)
        product = None

    # Activation steps: stored per-order instructions win, else derive
    # clean steps from the catalog product description.
    steps: list[str] = []

    def _as_steps(value) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [ln.strip(" •-\t") for ln in value.splitlines() if ln.strip(" •-\t")]
        if isinstance(value, (list, tuple)):
            return [str(s).strip() for s in value if str(s).strip()]
        return []

    steps = _as_steps(first.get("instructions_en")) or _as_steps(first.get("instructions_ar"))
    if not steps and product is not None:
        try:
            from services.product_spec import ProductSpecParser
            guide = ProductSpecParser.extract_clean_instructions(
                getattr(product, "description", None),
                getattr(product, "description_ar", None),
                getattr(product, "name", None) or product_name,
            )
            steps = list((guide or {}).get("steps_en") or [])
        except Exception as e:
            logging.debug("Could not extract instructions for order %s: %s", order.id, e)
            steps = []

    safe_name = html.escape(product_name, quote=False)
    lines = [
        f"✅ <b>Your order #{order.id} is ready!</b>",
        "",
        f"📦 <b>{safe_name}</b>",
        f"💰 Amount paid: <b>${amount:.2f}</b>",
    ]
    clean_goods = [str(g).strip() for g in (goods or []) if str(g).strip()]
    if clean_goods:
        lines += ["", "🔑 <b>Your credentials (tap to copy):</b>"]
        lines += [f"🔑 <code>{html.escape(g, quote=False)}</code>" for g in clean_goods[:20]]
    if steps:
        lines += ["", "📝 <b>Activation guide:</b>"]
        lines += [f"{i}. {html.escape(str(s).strip(), quote=False)}" for i, s in enumerate(steps[:10], 1)]
    lines += ["", "<i>Tap below to open your receipt in the Mini App.</i>"]
    text = "\n".join(lines)

    reply_markup = None
    try:
        tma_host = (getattr(config, "WEBHOOK_HOST", "") or "").strip().rstrip("/")
        if tma_host:
            from services.telegram_auth import generate_session_token
            auth_tok = generate_session_token(int(order.telegram_id))
            tma_url = (
                f"{tma_host}/app?tg_id={order.telegram_id}"
                f"&auth_token={auth_tok}&startapp=ord_{order.id}"
            )
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🧾 Open Receipt in Mini App",
                    web_app=WebAppInfo(url=tma_url),
                )
            ]])
    except Exception as e:
        logging.debug("Could not build Mini App receipt button for order %s: %s", order.id, e)
        reply_markup = None

    try:
        await NotificationService.send_to_user(text, order.telegram_id, reply_markup=reply_markup)
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

async def periodic_catalog_sync():
    """Periodically sync the BatStore catalog every hour to keep prices and stock fresh."""
    while True:
        await asyncio.sleep(3600)
        if config.BATSTORE_SYNC_ENABLED or getattr(config, "PRODSELLER_SYNC_ENABLED", True) or getattr(config, "G2BULK_SYNC_ENABLED", True):
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

    try:
        from services.g2bulk import G2BulkService
        g2b_data = await G2BulkService.get_balance(session)
        bal_g2b = float(g2b_data.get("balance") or 0.0)
        if bal_g2b < 5.0:
            await NotificationService.send_error_to_admins(
                "low_reseller_balance_g2bulk",
                f"⚠️ <b>Low Reseller Balance — سيرفر 3 (G2Bulk Games)</b>\n\n"
                f"• Current Balance: <b>${bal_g2b:.2f} USD</b>\n"
                f"• Alert Threshold: $5.00\n\n"
                "<i>Please top up your G2Bulk wallet via Telegram @G2BULKBOT.</i>",
                None,
                window_seconds=86400,
            )
    except Exception as e:
        logging.debug("Could not check G2Bulk balance: %s", e)

    return bal_bat

async def drain_retry_order_queue(session):
    """Legacy Redis entries may describe accepted purchases; quarantine them."""
    from repositories.batstore_product import BatStoreProductRepository
    from services.order_fulfillment import FulfillmentService, normalized_details
    import json
    redis = BatStoreProductRepository._redis
    if redis is None:
        return
    for _ in range(5):
        raw = await redis.lpop("ghstore:retry_order_queue")
        if not raw:
            break
        try:
            payload = json.loads(raw)
            order = await BatStoreOrderRepository.get_by_id(payload["order_id"], session)
            if order:
                for index, item in enumerate(normalized_details(order)):
                    if item.get("status") not in {"completed", "failed", "refunded", "cancelled"}:
                        await FulfillmentService.transition_item(order.id, index, "requires_manual_review", None, session)
                await session.commit()
        except Exception:
            await session.rollback()
            await redis.rpush("ghstore:retry_order_queue", raw)
            logging.exception("Could not quarantine legacy supplier retry")
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
