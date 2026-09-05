"""External Payment & Secondary Bot Webhook Endpoints."""
import logging

from fastapi import APIRouter, HTTPException, Request

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
    from bot import dp
    from services.multibot import MultibotService

    if not await MultibotService.has_token(bot_token):
        raise HTTPException(status_code=403, detail="Unregistered bot token")

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

    # Idempotency Lock: Deduplicate concurrent gateway retries
    lock = redis.lock(f"lock:webhook:sam:{invoice_id}", timeout=30)
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
                    # Cryptographic / Upstream Verification: prevent spoofed fake webhook calls
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
                    await NotificationService.send_to_admins(
                        f"💰 SAM invoice paid: {invoice_id} · tg:{payment.telegram_id} · "
                        f"{payment.usd_amount:.2f}$ · {txn_ref}", None)
                elif event == "invoice.expired":
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
    """Instant upstream webhook push receiver (BatStore / ProdSeller).

    Receives push events when async activation orders complete or fail upstream,
    fulfilling the order and delivering credentials instantly without polling lag.
    """
    from bot import bot
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored"}

    order_ref = str(body.get("order_id") or body.get("id") or body.get("external_id") or "").strip()
    status_str = str(body.get("status") or "").lower()

    if not order_ref:
        return {"status": "missing_ref"}

    async with get_db_session() as session:
        from models.batstore_order import BatStoreOrder
        from repositories.batstore_order import BatStoreOrderRepository
        from sqlalchemy import select

        stmt = select(BatStoreOrder).where(
            (BatStoreOrder.external_order_ref == order_ref) |
            (BatStoreOrder.customer_reference == order_ref)
        )
        order = (await session_execute(stmt, session)).scalar_one_or_none()
        if not order:
            logging.info("Supplier webhook for unknown order_ref=%s", order_ref)
            return {"status": "not_found"}

        if order.status == "completed":
            return {"status": "already_completed"}

        if status_str in ("completed", "success", "delivered", "active"):
            items_list = body.get("items") or body.get("order", {}).get("items") or []
            goods = [it.get("value") or it.get("data") or str(it) for it in items_list] if items_list else []
            if not goods and body.get("data"):
                goods = [str(body.get("data"))]

            details = order.details or []
            for item in details:
                if goods:
                    item["delivery_goods"] = goods
            order.status = "completed"
            order.details = details
            await BatStoreOrderRepository.update(order, session)
            await session_commit(session)

            goods_lines = "\n".join(f"• <code>{g}</code>" for g in goods) if goods else "تم تفعيل الخدمة بنجاح."
            first_name = details[0].get("name") if details else "المنتج"
            try:
                msg = (
                    f"🎉 <b>تم اكتمال وتفعيل طلبك #{order.id} بنجاح!</b>\n\n"
                    f"• <b>المنتج:</b> {first_name}\n\n"
                    f"📦 <b>بيانات التفعيل والتسليم:</b>\n{goods_lines}\n\n"
                    f"<i>(انقر على البيانات أعلاه للنسخ المباشر)</i>\n\n"
                    f"شكراً لصبرك وتسوقك مع GH Store! نتمنى لك تجربة ممتعة ✨"
                )
                await bot.send_message(chat_id=order.telegram_id, text=msg, parse_mode="HTML")
            except Exception as e:
                logging.warning("Could not send webhook fulfillment DM to %s: %s", order.telegram_id, e)

            try:
                from services.pdf_receipt import PDFReceiptService
                date_str = order.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if getattr(order, "created_at", None) else None
                await PDFReceiptService.dispatch_pdf_receipt(
                    order_id=order.id,
                    telegram_id=order.telegram_id,
                    order_data={"details": order.details, "total_sell": order.total_sell, "created_at": date_str, "goods": goods},
                    bot=bot
                )
            except Exception as e:
                logging.debug("Could not dispatch PDF receipt: %s", e)

            return {"status": "completed", "order_id": order.id}

        elif status_str in ("failed", "cancelled", "rejected"):
            from services.sale_pricing import externally_paid
            if not externally_paid(order):
                user = await UserRepository.get_by_tgid(order.telegram_id, session)
                if user:
                    user.top_up_amount = (user.top_up_amount or 0.0) + (order.total_sell or 0.0)
                    await UserRepository.update(user, session)
                    try:
                        await bot.send_message(
                            chat_id=order.telegram_id,
                            text=f"❌ تعذر تفعيل طلبك #{order.id} من قبل المورد. تمت إعادة مبلغ ${order.total_sell:.2f} إلى رصيدك المتاح."
                        )
                    except Exception:
                        pass
            order.status = "failed"
            await BatStoreOrderRepository.update(order, session)
            await session_commit(session)
            return {"status": "failed", "order_id": order.id}

    return {"status": "ignored"}
