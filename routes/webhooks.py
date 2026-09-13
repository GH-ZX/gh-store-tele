"""External Payment & Secondary Bot Webhook Endpoints."""
import logging

import os
import hmac
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import config
from db import get_db_session, session_commit, session_execute
from repositories.sam_payment import SamPaymentRepository
from repositories.user import UserRepository
from services.notification import NotificationService
from services.referral import ReferralService

router = APIRouter(tags=["webhooks"])

_mirror_bots: dict = {}


def get_mirror_bot(token: str):
    if token not in _mirror_bots:
        from aiogram import Bot as _AiogramBot
        from bot import session
        _mirror_bots[token] = _AiogramBot(token=token, session=session)
    return _mirror_bots[token]


@router.post("/webhook/bot/{bot_token}")
async def mirror_bot_webhook(bot_token: str, request: Request):
    """Route updates for secondary/mirror clone bots through the primary Aiogram dispatcher."""
    import secrets
    from bot import dp
    from services.multibot import MultibotService

    if not await MultibotService.has_token(bot_token):
        raise HTTPException(status_code=403, detail="Unregistered bot token")
    expected_mirror = (config.WEBHOOK_SECRET_TOKEN or "").strip()
    if expected_mirror:
        got = request.headers.get("X-Telegram-Bot-Api-Secret-Token") or ""
        if not secrets.compare_digest(got, expected_mirror):
            raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        mirror_bot = get_mirror_bot(bot_token)
        update_data = await request.json()
        await dp.feed_webhook_update(mirror_bot, update_data)
    except Exception as e:
        logging.error("Mirror bot webhook error for token %s: %s", bot_token[:8], e)
    return {"status": "ok"}


@router.post("/samwebhook")
async def sam_webhook(request: Request):
    """SAM (sam-api.pro) payment webhook.

    Events: invoice.paid | invoice.expired. On payment we credit the customer's
    bot balance (usd_amount) and notify them. SAM requires a 2xx answer always.
    """
    from bot import bot, redis

    try:
        body = await request.json()
    except Exception:
        return {"status": "ok"}

    event = body.get("event")
    invoice_id = body.get("invoiceId") or body.get("invoice_id")
    txn_ref = body.get("transactionRef") or body.get("transaction_ref")
    if not invoice_id:
        return {"status": "ok"}

    lock = redis.lock(f"lock:sam:invoice:{invoice_id}", timeout=30)
    acquired = await lock.acquire(blocking=False)
    if not acquired:
        return {"status": "ok", "message": "already_processing"}

    try:
        async with get_db_session() as session:
            try:
                payment = await SamPaymentRepository.get_by_invoice_id(invoice_id, session)
                if payment is None:
                    logging.warning("SAM webhook for unknown invoice %s", invoice_id)
                    return {"status": "ok"}

                if event == "invoice.paid" and payment.event != "invoice.paid":
                    from services.sam import SamService
                    try:
                        upstream_info = await SamService.get_invoice(session, invoice_id)
                        upstream_status = (upstream_info.get("status") or "").lower()
                        if upstream_status != "paid":
                            logging.warning("Rejected spoofed SAM webhook for invoice %s (upstream status=%s)", invoice_id, upstream_status)
                            return {"status": "unverified"}
                        txn_ref = upstream_info.get("transactionRef") or txn_ref
                    except Exception as verify_err:
                        logging.warning("Could not verify SAM webhook upstream for %s: %s", invoice_id, verify_err)
                        return {"status": "upstream_check_failed"}

                    claimed = await SamPaymentRepository.mark_event_if_not_paid(invoice_id, "invoice.paid", txn_ref, session)
                    if not claimed:
                        return {"status": "ok", "message": "already_paid"}
                    user = await UserRepository.get_by_tgid(payment.telegram_id, session)
                    if user is not None:
                        await ReferralService.apply_deposit_referral(payment.usd_amount, user, session)
                        await session_commit(session)
                        sym = config.CURRENCY.get_localized_symbol()
                        caption = f"✅ Top-up via {payment.method}:\n{payment.usd_amount:.2f}{sym} added to your balance."
                        try:
                            await bot.send_message(payment.telegram_id, caption)
                        except Exception as e:
                            logging.error("Failed to notify SAM payer %s: %s", payment.telegram_id, e)
                    else:
                        logging.error("SAM payer user not found: %s", payment.telegram_id)
                        await session_commit(session)
                    await NotificationService.send_to_admins(
                        f"💰 SAM invoice paid: {invoice_id} · tg:{payment.telegram_id} · "
                        f"{payment.usd_amount:.2f}$ · {txn_ref}", None)
                elif event == "invoice.expired":
                    if payment.event == "invoice.paid":
                        return {"status": "ok", "message": "already_paid"}
                    await NotificationService.send_to_admins(
                        f"⏰ SAM invoice expired: {invoice_id} · tg:{payment.telegram_id}", None)
                    await SamPaymentRepository.mark_event(invoice_id, event, txn_ref, session)
                    await session_commit(session)
            except Exception as e:
                logging.error("SAM webhook processing error: %s", e, exc_info=True)
    finally:
        try:
            await lock.release()
        except Exception:
            pass

    return {"status": "ok"}


@router.post("/api/supplier/webhook/{supplier}")
async def supplier_order_webhook(supplier: str, request: Request):
    """Instant upstream webhook push receiver (BatStore / ProdSeller)."""
    from bot import bot
    req_headers = getattr(request, "headers", {}) or {}
    req_query = getattr(request, "query_params", {}) or {}
    secret_header = (
        req_headers.get("X-Supplier-Webhook-Secret")
        or req_headers.get("X-Webhook-Secret")
        or req_query.get("secret")
        or req_query.get("token")
        or ""
    ).strip()

    async with get_db_session() as session:
        from services.config import ConfigService
        expected_secret = (await ConfigService.get(
            session, "SUPPLIER_WEBHOOK_SECRET",
            env_fallback=os.environ.get("SUPPLIER_WEBHOOK_SECRET", "")
        ) or "").strip()
        if not expected_secret or not secret_header or not hmac.compare_digest(secret_header, expected_secret):
            logging.warning("Unauthorized supplier webhook attempt for supplier=%s", supplier)
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        try:
            body = await request.json()
        except Exception:
            return {"status": "ignored"}

        order_ref = str(body.get("order_id") or body.get("id") or body.get("external_id") or "").strip()
        status_str = str(body.get("status") or "").lower()
        if not order_ref:
            return {"status": "missing_ref"}

        if supplier not in {"batstore", "prodseller", "g2bulk"}:
            return JSONResponse({"error": "unknown_supplier"}, status_code=404)
        from sqlalchemy import select, cast, or_
        from sqlalchemy.dialects.postgresql import JSONB
        from models.order import Order
        from services.order_fulfillment import FulfillmentService, normalized_details
        refs = [order_ref]
        if supplier == "g2bulk":
            refs.extend([f"g2b-game-{order_ref}", f"g2b-vouch-{order_ref}"])
        # Provider and reference must belong to the same line. Never resolve a
        # cart by only its aggregate reference or customer-controlled identity.
        conditions = [cast(Order.details, JSONB).contains([
            {"supplier": supplier, "external_order_ref": ref}
        ]) for ref in refs]
        candidates = (await session.execute(select(Order).where(or_(*conditions)))).scalars().all()
        matches = [(order, index, item) for order in candidates
                   for index, item in enumerate(normalized_details(order))
                   if item.get("supplier") == supplier and str(item.get("external_order_ref") or "") in refs]
        if len(matches) != 1:
            return {"status": "not_found" if not matches else "ambiguous_reference"}
        order, index, item = matches[0]
        # Treat callbacks as a wake-up signal. Fetch authoritative status and
        # goods, preventing one compromised shared-secret sender forging a
        # different provider's delivery or refund.
        try:
            import asyncio
            upstream_status, goods = await asyncio.wait_for(
                FulfillmentService.supplier_status(item, session), timeout=15)
        except Exception:
            logging.exception("Could not verify supplier callback for order %s", order.id)
            return JSONResponse({"status": "verification_unavailable"}, status_code=503)
        upstream_status = str(upstream_status).lower()
        if upstream_status in {"completed", "success", "delivered", "active"}:
            status = "completed"
        elif upstream_status in {"failed", "cancelled", "rejected", "refunded"}:
            status = "failed"
        else:
            return {"status": "pending"}
        updated, changed = await FulfillmentService.transition_item(
            order.id, index, status, goods, session,
            external_ref=item["external_order_ref"], supplier=supplier)
        await session.commit()
        if changed and updated.status == "completed":
            from services.order_polling import _notify_order_complete
            await _notify_order_complete(updated, [
                good for detail in updated.details for good in detail.get("delivery_goods", [])
            ])
        return {"status": updated.status, "order_id": updated.id, "changed": changed}
