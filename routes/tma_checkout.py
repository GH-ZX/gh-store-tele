"""TMA Orders, Checkout, Cart, Quotes, and Support Ticket API Routes."""
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


@router.post("/api/buy")
async def tma_instant_buy(request: Request):
    """In-app checkout for Telegram Mini App. Customers stay in the app without text chat redirect."""
    from bot import redis

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    product_id = int(body.get("product_id") or 0)
    quantity = max(1, min(10, int(body.get("quantity") or 1)))

    if not tg_id or not product_id:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    # Concurrency Lock: prevent double-tap race conditions
    lock = redis.lock(f"lock:checkout:{tg_id}", timeout=15)
    acquired = await lock.acquire(blocking=False)
    if not acquired:
        return JSONResponse(
            {"error": "checkout_in_progress", "message": "Another checkout is currently processing for this user."},
            status_code=409,
        )

    try:
        async with get_db_session() as session:
            user = await UserRepository.get_by_tgid(tg_id, session)
            if not user:
                return JSONResponse({"error": "user_not_found"}, status_code=404)

            product = await BatStoreProductRepository.get_by_product_id(product_id, session)
            if not product or product.hidden:
                return JSONResponse({"error": "product_not_found"}, status_code=404)

            tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0), getattr(user, "custom_discount_pct", None))
            coupon_code = (body.get("coupon_code") or "").strip()
            coupon_type = coupon_value = None
            if coupon_code:
                from repositories.coupon import CouponRepository
                coupon = await CouponRepository.get_by_code(coupon_code, session)
                if coupon and coupon.is_active:
                    if not (coupon.usage_limit and coupon.usage_count >= coupon.usage_limit):
                        coupon_type, coupon_value = coupon.type, float(coupon.value or 0.0)

            line_inputs = [(product.sell_price_usd, product.cost_usd, quantity,
                            BatStoreService.get_volume_discount(quantity))]
            try:
                line_totals, _ = price_lines(
                    line_inputs, discount_pct=discount_pct,
                    coupon_type=coupon_type, coupon_value=coupon_value or 0,
                )
            except ValueError as e:
                if str(e) == "price_unavailable":
                    return JSONResponse({"error": "price_unavailable"}, status_code=400)
                raise
            total = round(float(line_totals[0]), 2)

            if coupon_code and coupon_type is not None:
                from repositories.coupon import CouponRepository
                coupon = await CouponRepository.get_by_code(coupon_code, session)
                if coupon and coupon.is_active:
                    await CouponRepository.increment_usage(coupon.id, session)

            debited = await UserRepository.try_debit_balance(user.telegram_id, total, session)
            if not debited:
                available = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
                return JSONResponse({
                    "error": "insufficient_balance",
                    "needed": total,
                    "available": available,
                    "shortage": round(total - available, 2)
                }, status_code=400)
            await session_commit(session)

            cust_ref = f"tma-{user.telegram_id}-{uuid.uuid4().hex[:8]}"
            idempotency_key = cust_ref

            wholesale_cost = float(product.cost_usd or 0.0) * quantity
            from services.multi_supplier import MultiSupplierService
            supp_balance = await MultiSupplierService.get_cached_supplier_balance(product, session)

            needs_recharge = (supp_balance < wholesale_cost)
            placed = None
            goods_list = []
            upstream_id = ""
            order_status = "completed" if product.delivery_type in ("stock", "supplier_api") else "pending_fulfillment"

            if not needs_recharge:
                try:
                    placed_result = await MultiSupplierService.place_order_with_failover(
                        session, product, quantity,
                        customer_reference=cust_ref,
                        idempotency_key=idempotency_key,
                    )
                    upstream_id = str(placed_result.get("external_order_ref") or "")
                    goods_list = placed_result.get("goods") or []
                    order_status = "completed" if goods_list else "pending_fulfillment"
                except Exception as e:
                    logging.warning("Multi-supplier placement error on buy, queueing for admin recharge: %s", e)
                    needs_recharge = True

            if needs_recharge:
                order_status = "pending_supplier_recharge"

            order_dto = BatStoreOrderDTO(
                telegram_id=user.telegram_id,
                total_sell=total,
                status=order_status,
                external_order_ref=upstream_id,
                customer_reference=cust_ref,
                details=[{
                    "product_id": product.product_id,
                    "name": product.name,
                    "quantity": quantity,
                    "cost_usd": product.cost_usd,
                    "sell_usd": total,
                    "delivery_type": product.delivery_type,
                    "delivery_goods": goods_list,
                    "warranty_days": product.warranty_days or 0,
                }],
            )
            order = await BatStoreOrderRepository.create(order_dto, session)
            await session_commit(session)

            if needs_recharge:
                from services.supplier_recharge import SupplierRechargeService
                await SupplierRechargeService.notify_customer_order_queued(order.id, product.name, user.telegram_id)
                await SupplierRechargeService.notify_admin_recharge_needed(order, product, quantity, wholesale_cost, user)
                return {
                    "status": "success",
                    "order_id": order.id,
                    "product_name": product.name,
                    "quantity": quantity,
                    "total_paid": total,
                    "sym": config.CURRENCY.get_localized_symbol(),
                    "goods": [],
                    "reseller_status": "pending_supplier_recharge",
                    "message": "تم استلام وتأكيد طلبك بنجاح! جاري التجهيز والتسليم فور اكتمال التفعيل."
                }
            # Process 0.2% referral commission from margin
            if getattr(user, "referred_by_user_id", None):
                try:
                    referrer = await UserRepository.get_by_id(user.referred_by_user_id, session)
                    if referrer:
                        margin_profit = max(0.0, total - (float(product.cost_usd or 0.0) * quantity))
                        ref_rate_cfg = await ConfigService.get(session, "REFERRAL_MARGIN_COMMISSION_PERCENT", default="0.2")
                        ref_rate = float(ref_rate_cfg or 0.2) / 100.0
                        commission = round(margin_profit * ref_rate, 3)
                        if commission > 0.001:
                            await UserRepository.refund_balance(referrer.telegram_id, commission, session)
                            from models.referral import ReferralBonusDTO
                            from repositories.referral import ReferralRepository
                            await ReferralRepository.create(ReferralBonusDTO(
                                referral_user_id=user.id,
                                referrer_user_id=referrer.id,
                                payment_amount=total,
                                applied_referral_bonus=0.0,
                                applied_referrer_bonus=commission,
                            ), session)
                            await session_commit(session)
                            try:
                                await NotificationService.send_to_user(
                                    f"🎁 <b>عمولة إحالة جديدة!</b>\n\nقام صديقك المدعو بإتمام طلب بقيمة ${total:.2f}.\nتمت إضافة <b>+${commission:.3f}</b> إلى رصيدك!",
                                    referrer.telegram_id
                                )
                            except Exception:
                                pass
                except Exception as e:
                    logging.error("Failed to process referral margin commission: %s", e)

            return {
                "status": "success",
                "order_id": order.id,
                "product_name": product.name,
                "quantity": quantity,
                "total_paid": total,
                "sym": config.CURRENCY.get_localized_symbol(),
                "goods": goods_list,
                "reseller_status": order_status,
            }
    finally:
        try:
            await lock.release()
        except Exception:
            pass


@router.post("/api/cart/checkout")
async def tma_cart_checkout(request: Request):
    """Atomic multi-item checkout for the Telegram Mini App Cart Drawer."""
    from bot import redis

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

    # Concurrency Lock: prevent double-tap race conditions
    lock = redis.lock(f"lock:checkout:{tg_id}", timeout=20)
    acquired = await lock.acquire(blocking=False)
    if not acquired:
        return JSONResponse(
            {"error": "checkout_in_progress", "message": "Another checkout is currently processing for this user."},
            status_code=409,
        )

    try:
        async with get_db_session() as session:
            user = await UserRepository.get_by_tgid(tg_id, session)
            if not user:
                return JSONResponse({"error": "user_not_found"}, status_code=404)

            cart_products = []
            price_inputs = []
            for it in items_input:
                pid = int(it.get("product_id") or 0)
                qty = max(1, min(20, int(it.get("quantity") or 1)))
                prod = await BatStoreProductRepository.get_by_product_id(pid, session)
                if not prod or prod.hidden:
                    return JSONResponse({"error": f"Product #{pid} is unavailable"}, status_code=400)
                cart_products.append({"product": prod, "quantity": qty})
                price_inputs.append((prod.sell_price_usd, prod.cost_usd, qty,
                                    BatStoreService.get_volume_discount(qty)))

            tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0), getattr(user, "custom_discount_pct", None))
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
                    coupon_type=coupon_type, coupon_value=coupon_value or 0,
                )
            except ValueError as e:
                if str(e) == "price_unavailable":
                    return JSONResponse({"error": "price_unavailable"}, status_code=400)
                raise
            for cp, line_total in zip(cart_products, line_totals):
                cp["line_total"] = float(line_total)
            total = round(float(sum(line_totals)), 2)
            if coupon_code and coupon_type is not None:
                from repositories.coupon import CouponRepository
                coupon = await CouponRepository.get_by_code(coupon_code, session)
                if coupon and coupon.is_active:
                    await CouponRepository.increment_usage(coupon.id, session)

            debited = await UserRepository.try_debit_balance(user.telegram_id, total, session)
            if not debited:
                available = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
                return JSONResponse({
                    "error": "insufficient_balance",
                    "needed": total,
                    "available": available,
                    "shortage": round(total - available, 2)
                }, status_code=400)
            await session_commit(session)

            all_goods = []
            order_details = []
            for cp in cart_products:
                prod = cp["product"]
                qty = cp["quantity"]
                cust_ref = f"cart-{user.telegram_id}-{uuid.uuid4().hex[:8]}"
                goods_list = []
                try:
                    from services.multi_supplier import MultiSupplierService
                    placed_result = await MultiSupplierService.place_order_with_failover(
                        session, prod, qty,
                        customer_reference=cust_ref,
                        idempotency_key=cust_ref
                    )
                    goods_list = placed_result.get("goods") or []
                    all_goods.extend(goods_list)
                except Exception as e:
                    logging.error("Failed to place item #%s in cart checkout: %s", prod.product_id, e)

                order_details.append({
                    "product_id": prod.product_id,
                    "name": prod.name,
                    "quantity": qty,
                    "cost_usd": prod.cost_usd,
                    "sell_usd": cp["line_total"],
                    "delivery_type": prod.delivery_type,
                    "delivery_goods": goods_list,
                    "warranty_days": prod.warranty_days or 0
                })

            order = await BatStoreOrderRepository.create(BatStoreOrderDTO(
                telegram_id=user.telegram_id,
                total_sell=total,
                status="completed",
                customer_reference=f"cart-{uuid.uuid4().hex[:10]}",
                details=order_details
            ), session)
            await session_commit(session)

            try:
                await redis.delete(f"ghstore:tma_cart:{user.telegram_id}")
            except Exception:
                pass

            sym = config.CURRENCY.get_localized_symbol()
            return {
                "status": "success",
                "order_id": order.id,
                "total_paid": total,
                "sym": sym,
                "goods": all_goods,
                "items_count": len(cart_products)
            }
    finally:
        try:
            await lock.release()
        except Exception:
            pass


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
            price_inputs.append((prod.sell_price_usd, prod.cost_usd, qty,
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

    tg_id = int(body.get("tg_id") or 0)
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


@router.get("/api/orders/{order_id}/receipt.pdf")
async def get_order_receipt_pdf(order_id: int, request: Request, tg_id: int | None = None):
    """Serve official vector-rendered PDF invoice for customer orders."""
    from fastapi import Response
    try:
        user_id = extract_and_verify_telegram_user(request, tg_id)
    except Exception:
        user_id = tg_id

    async with get_db_session() as session:
        order = await BatStoreOrderRepository.get_by_id(order_id, session)
        if not order:
            return JSONResponse({"error": "order_not_found"}, status_code=404)

        from services.pdf_receipt import PDFReceiptService
        date_str = order.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if getattr(order, "created_at", None) else None
        pdf_bytes = PDFReceiptService.generate_receipt_bytes(order.id, {
            "telegram_id": order.telegram_id,
            "total_sell": order.total_sell,
            "created_at": date_str,
            "details": order.details or [],
        })

    filename = f"GHStore_Receipt_Order_{order_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
            "Cache-Control": "public, max-age=86400",
        }
    )
