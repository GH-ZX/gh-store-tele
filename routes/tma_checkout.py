"""TMA Orders, Checkout, Cart, Quotes, and Support Ticket API Routes."""
import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

import config
from db import get_db_session, session_commit, session_execute
from models.batstore_order import BatStoreOrderDTO
from repositories.batstore_order import BatStoreOrderRepository
from repositories.batstore_product import BatStoreProductRepository
from repositories.user import UserRepository
from services.batstore import BatStoreService
from services.notification import NotificationService
from services.sale_pricing import price_lines
from services.telegram_auth import extract_and_verify_telegram_user
from services.user import get_vip_tier_info

router = APIRouter(tags=["checkout"])


async def _send_order_delivery_receipt_telegram(telegram_id: int, order_id: int, product_name: str, total_paid: float, goods_list: list, instructions_list: list = None):
    """Send real-time Telegram receipt and keys directly to user chat on MiniApp purchase."""
    from bot import bot
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    from routes.common import normalize_delivery_good
    from services.telegram_auth import generate_session_token

    try:
        tma_host = (config.WEBHOOK_HOST or "").strip().rstrip('/')
        auth_tok = generate_session_token(telegram_id)
        ord_url = f"{tma_host}/app?tg_id={telegram_id}&auth_token={auth_tok}&startapp=ord_{order_id}"

        keys_text = ""
        if goods_list:
            clean_keys = [normalize_delivery_good(g) for g in goods_list[:4]]
            clean_keys = [k for k in clean_keys if k]
            if clean_keys:
                keys_text = "\n".join(f"<code>{k}</code>" for k in clean_keys)

        msg = (
            f"🎉 <b>تم تأكيد واستلام طلبك بنجاح! | Order Confirmed</b>\n\n"
            f"📦 <b>رقم الطلب:</b> #{order_id}\n"
            f"🛍️ <b>المنتج:</b> {product_name}\n"
            f"💰 <b>المبلغ:</b> ${total_paid:.2f} USD\n"
        )
        if keys_text:
            msg += f"\n🔑 <b>بيانات التفعيل / الاستلام:</b>\n{keys_text}\n"
        if instructions_list:
            steps_formatted = "\n".join(f"• {s}" for s in instructions_list[:3])
            msg += f"\n📋 <b>خطوات التفعيل والاستخدام:</b>\n{steps_formatted}\n"

        msg += "\n💡 <i>يمكنك متابعة تفاصيل وضمان هذا الطلب دائماً عبر زر المتجر أدناه.</i>"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 تفاصيل الطلب والإيصال", web_app=WebAppInfo(url=ord_url))]
        ])

        await bot.send_message(chat_id=telegram_id, text=msg, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logging.debug("Could not push Telegram order delivery receipt to %s: %s", telegram_id, e)

async def _durable_checkout(request: Request, *, cart: bool = False):
    from services.checkout import CheckoutService
    from services.order_fulfillment import FulfillmentService

    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("invalid_json")
        claimed_id = int(body.get("tg_id") or 0)
    except (ValueError, TypeError):
        return JSONResponse({"error": "invalid_parameters"}, status_code=400)
    try:
        tg_id = extract_and_verify_telegram_user(request, claimed_id)
        key = request.headers.get("Idempotency-Key", "")
        async with get_db_session() as session:
            try:
                order, created = await CheckoutService.reserve(tg_id, body, key, session, cart=cart)
            except Exception:
                await session.rollback()
                raise
            if created:
                order = await FulfillmentService.fulfill_order(order.id, session)
                await session.commit()
            result = CheckoutService.response(order)
            result["sym"] = config.CURRENCY.get_localized_symbol()
            if created and order.status == "completed":
                asyncio.create_task(_send_order_delivery_receipt_telegram(
                    telegram_id=tg_id, order_id=order.id,
                    product_name=result["product_name"], total_paid=order.total_sell,
                    goods_list=result["goods"],
                    instructions_list=result["instructions_ar"] or result["instructions_en"],
                ))
            if created:
                # Cart cleanup is not part of payment correctness.
                try:
                    from bot import redis
                    await redis.delete(f"ghstore:tma_cart:{tg_id}")
                except Exception:
                    logging.debug("Could not clear checkout cart cache", exc_info=True)
            return result
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@router.post("/api/buy")
async def tma_instant_buy(request: Request):
    return await _durable_checkout(request)


@router.post("/api/cart/checkout")
async def tma_cart_checkout(request: Request):
    return await _durable_checkout(request, cart=True)


@router.post("/api/cart/sync")
async def tma_cart_sync(request: Request):
    """Sync client-side TMA cart to Redis for abandoned cart recovery notifications."""
    from bot import redis

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    items = body.get("items") or []
    key = f"ghstore:tma_cart:{tg_id}"
    if not items:
        try:
            await redis.delete(key)
        except Exception:
            pass
        return {"status": "cleared"}

    cart_data = {
        "tg_id": tg_id,
        "items": items,
        "updated_at": time.time()
    }
    try:
        await redis.setex(key, 604800, json.dumps(cart_data))
    except Exception as e:
        logging.warning("Failed to sync TMA cart to Redis: %s", e)
    return {"status": "synced", "items_count": len(items)}


@router.post("/api/price-quote")
async def tma_price_quote(request: Request):
    """Authoritative cost-floored quote shared by checkout; never exposes supplier costs."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    items_input = body.get("items") or []
    if not tg_id or not items_input:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session) if tg_id else None
        if user:
            _, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0),
                                                getattr(user, "custom_discount_pct", None))
        else:
            discount_pct = 0.0
        price_inputs, quote_meta = [], []
        for it in items_input:
            pid = int(it.get("product_id") or 0)
            qty = max(1, min(20, int(it.get("quantity") or 1)))
            prod = await BatStoreProductRepository.get_by_product_id(pid, session)
            if not prod or prod.hidden:
                return JSONResponse({"error": f"Product #{pid} is unavailable"}, status_code=400)
            from services.checkout import priced_product
            try:
                _, quote_cost, unit_price = await priced_product(prod, it, user, session)
            except (ValueError, TypeError) as exc:
                return JSONResponse({"error": str(exc)}, status_code=400)
            price_inputs.append((unit_price, quote_cost, qty,
                                BatStoreService.get_volume_discount(qty)))
            quote_meta.append({"product_id": pid, "quantity": qty})
        coupon_code = (body.get("coupon_code") or "").strip()
        coupon_type = coupon_value = None
        if coupon_code:
            from repositories.coupon import CouponRepository
            coupon = await CouponRepository.get_by_code(coupon_code, session)
            if coupon and coupon.is_active:
                if not (coupon.usage_limit and coupon.usage_count >= coupon.usage_limit):
                    coupon_type, coupon_value = coupon.type, float(coupon.value or 0.0)
        try:
            line_totals, discount_limited = price_lines(
                price_inputs, discount_pct=discount_pct,
                coupon_type=coupon_type, coupon_value=coupon_value or 0)
        except ValueError as e:
            if str(e) == "price_unavailable":
                return JSONResponse({"error": "price_unavailable"}, status_code=400)
            raise
        lines = [{**meta, "total": float(total)} for meta, total in zip(quote_meta, line_totals)]
    return {"total": round(float(sum(line_totals)), 2), "lines": lines, "discount_limited": discount_limited}


@router.post("/api/coupon/validate")
async def tma_validate_coupon(request: Request):
    """Validate a promo/coupon code and compute discount for Mini App checkout."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    code = (body.get("code") or "").strip()
    subtotal = float(body.get("subtotal") or 0.0)
    if not code:
        return JSONResponse({"error": "missing_code"}, status_code=400)

    from repositories.coupon import CouponRepository
    async with get_db_session() as session:
        coupon = await CouponRepository.get_by_code(code, session)
        if not coupon or not coupon.is_active:
            return JSONResponse({"valid": False, "error": "كود الخصم غير صالح أو منتهي الصلاحية"}, status_code=400)

        if coupon.usage_limit and coupon.usage_count >= coupon.usage_limit:
            return JSONResponse({"valid": False, "error": "تم استنفاد الحد الأقصى لاستخدام هذا الكود"}, status_code=400)

        from services.sale_pricing import normalize_coupon_type
        discount = 0.0
        if normalize_coupon_type(coupon.type) == "PERCENTAGE":
            discount = round(subtotal * (float(coupon.value) / 100.0), 2)
        else:
            discount = round(float(coupon.value), 2)

        discount = min(discount, subtotal)
        new_total = max(0.01, round(subtotal - discount, 2))

    return {
        "valid": True,
        "code": coupon.code,
        "type": coupon.type.value if hasattr(coupon.type, "value") else str(coupon.type),
        "value": float(coupon.value),
        "discount": discount,
        "new_total": new_total,
        "message": f"تم تطبيق كود الخصم بنجاح (-${discount:.2f})!"
    }


@router.post("/api/warranty/claim")
async def tma_claim_warranty(request: Request):
    """Claim warranty replacement directly from inside the Mini App."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)
    order_id = int(body.get("order_id") or 0)

    async with get_db_session() as session:
        order = await BatStoreOrderRepository.get_by_id(order_id, session)
        if not order or order.telegram_id != tg_id or order.status != "completed":
            return JSONResponse({"error": "order_not_eligible"}, status_code=400)
        if getattr(order, "warranty_claimed", False):
            return JSONResponse({"error": "already_claimed"}, status_code=400)

        details = order.details or []
        pid = details[0].get("product_id") if details else None
        if not pid:
            return JSONResponse({"error": "missing_product_info"}, status_code=400)

        repl_ref = f"warranty-tma-{order.id}-{tg_id}"
        try:
            placed = await BatStoreService.place_order(
                session, pid, 1,
                customer_reference=repl_ref,
                idempotency_key=repl_ref,
            )
            items = placed.get("order", {}).get("items") or []
            goods_list = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
            await BatStoreOrderRepository.mark_warranty_claimed(order.id, True, session)
            await session_commit(session)
            await NotificationService.send_to_admins(
                f"🛡️ Automated warranty issued for #{order.id} (tg:{tg_id}) via Mini App",
                None
            )
            return {"status": "success", "goods": goods_list}
        except Exception as e:
            await BatStoreOrderRepository.mark_warranty_claimed(order.id, True, session)
            await session_commit(session)
            await NotificationService.send_to_admins(
                f"🛡️ Manual warranty claim for #{order.id} (tg:{tg_id}) via Mini App: {e}",
                None
            )
            return {"status": "pending_manual_review"}


@router.post("/api/restock/subscribe")
async def tma_restock_subscribe(request: Request):
    """Subscribe user to in-app restock notification when out-of-stock product returns."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = int(body.get("tg_id") or 0)
    product_id = int(body.get("product_id") or 0)
    if not tg_id or not product_id:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        user_id = user.id if user else None
        lang = user.language if user and user.language else "ar"

        from repositories.restock_subscription import RestockSubscriptionRepository
        await RestockSubscriptionRepository.subscribe(
            telegram_id=tg_id,
            user_id=user_id,
            batstore_product_id=product_id,
            subcategory_id=None,
            language=lang,
            session=session
        )
        await session_commit(session)

    return {"status": "success", "message": "تم تفعيل التنبيه فور توفر المنتج بنجاح!"}


@router.post("/api/support/ticket")
async def submit_support_ticket(request: Request):
    """In-app customer support inquiry dispatched to admin Telegram topic."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    subject = str(body.get("subject") or "استفسار عام / General Inquiry").strip()
    message = str(body.get("message") or "").strip()
    order_id = body.get("order_id")

    if not message or len(message) < 3:
        return JSONResponse({"error": "message_too_short"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        username_str = f"@{user.telegram_username}" if (user and user.telegram_username) else f"tg:{tg_id}"
        ticket_id = int(time.time()) % 100000
        ticket_card = (
            f"🎫 <b>تذكرة دعم فني جديدة #{ticket_id}</b>\n\n"
            f"• <b>العميل:</b> {username_str} (<code>{tg_id}</code>)\n"
            f"• <b>الطلب المتعلق:</b> #{order_id or 'لا يوجد'}\n"
            f"• <b>الموضوع:</b> {subject}\n\n"
            f"📝 <b>نص الرسالة:</b>\n{message}"
        )
        await NotificationService.send_to_admins(ticket_card, None)
    return {"status": "success", "ticket_id": ticket_id}
