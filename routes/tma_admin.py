"""TMA Admin Control Center API Routes."""
import asyncio
import csv
import datetime
import io
import json
import logging
import os
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

import config
from db import get_db_session, session_commit, session_execute
from models.admin_audit_log import AdminAuditLog
from models.batstore_order import BatStoreOrder, BatStoreOrderDTO
from models.batstore_product import BatStoreProduct, BatStoreProductDTO
from models.coupon import Coupon, CouponDTO
from models.sam_payment import SamPayment
from models.stars_payment import StarsPayment
from models.storefront_category import StorefrontCategory
from models.user import User
from repositories.batstore_order import BatStoreOrderRepository
from repositories.batstore_product import BatStoreProductRepository
from repositories.coupon import CouponRepository
from repositories.referral_withdrawal import ReferralWithdrawalRepository
from repositories.user import UserRepository
from routes.common import verify_admin
from routes.tma_catalog import invalidate_catalog_cache, invalidate_admin_stats_cache
from services.batstore import BatStoreService
from services.config import CONFIG_DEFINITIONS, ConfigService
from services.multi_supplier import MultiSupplierService
from services.notification import NotificationService
from services.prodseller import ProdSellerService
from services.sale_pricing import externally_paid, order_cost
from utils.telegram import clean_tg_emojis

router = APIRouter(tags=["admin"])

@router.get("/api/admin/search/demands")
async def get_admin_search_demands(tg_id: int):
    if not verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    from bot import redis
    demands = []
    if redis:
        try:
            items = await redis.zrevrange("ghstore_search_demands", 0, 14, withscores=True)
            for query, score in items:
                q_str = query.decode("utf-8") if isinstance(query, bytes) else str(query)
                demands.append({"query": q_str, "searches": int(score)})
        except Exception as e:
            logging.warning("Failed to fetch search demands: %s", e)

    return {"status": "ok", "demands": demands}


async def _run_admin_broadcast(broadcast_id: str, message: str, target_segment: str):
    """Rate-limited background broadcast runner (~25 msgs/sec)."""
    from bot import bot, redis
    try:
        async with get_db_session() as session:
            stmt = select(User).where(User.can_receive_messages == True, User.is_banned == False)
            if target_segment == "buyers":
                stmt = stmt.where(User.consume_records > 0)
            elif target_segment == "zero_balance":
                stmt = stmt.where((User.top_up_amount - User.consume_records) <= 0)

            users = (await session_execute(stmt, session)).scalars().all()
            total = len(users)
            sent = 0
            failed = 0

            for u in users:
                try:
                    await bot.send_message(u.telegram_id, message, parse_mode="HTML")
                    sent += 1
                except Exception:
                    failed += 1
                await asyncio.sleep(0.04)

            if redis:
                await redis.setex(
                    f"ghstore:broadcast:{broadcast_id}",
                    86400,
                    json.dumps({
                        "active": False,
                        "sent": sent,
                        "total": total,
                        "failed": failed,
                        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    })
                )
    except Exception as e:
        logging.error("Broadcast %s failed: %s", broadcast_id, e)


@router.post("/api/admin/manual-sale")
async def admin_manual_sale(request: Request):
    """Admin-recorded externally paid sale at regular list price."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_tg_id = int(body.get("admin_tg_id") or 0)
    if not verify_admin(admin_tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    product_id = int(body.get("product_id") or 0)
    qty = max(1, min(10, int(body.get("quantity") or 1)))
    target_tg_id = int(body.get("target_tg_id") or admin_tg_id)
    payment_confirmed = body.get("payment_confirmed") is True
    if not product_id or not target_tg_id:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)
    if not payment_confirmed:
        return JSONResponse({"error": "payment_confirmation_required"}, status_code=400)

    async with get_db_session() as session:
        prod = await BatStoreProductRepository.get_by_product_id(product_id, session)
        if not prod:
            return JSONResponse({"error": "product_not_found"}, status_code=404)
        recipient = await UserRepository.get_by_tgid(target_tg_id, session)
        if not recipient:
            return JSONResponse({"error": "recipient_not_found"}, status_code=404)

        total = float((Decimal(str(prod.sell_price_usd)) * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        cust_ref = f"admin-sale-{product_id}-{target_tg_id}-{uuid.uuid4().hex[:6]}"
        goods_list = []
        order_status = "completed" if prod.delivery_type in ("stock", "supplier_api") else "pending_fulfillment"
        external_ref = None
        try:
            placed = await BatStoreService.place_order(
                session, prod.product_id, qty,
                customer_reference=cust_ref,
                idempotency_key=cust_ref
            )
            external_ref = placed.get("order", {}).get("id") or placed.get("order_id")
            items = placed.get("order", {}).get("items") or []
            goods_list = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
            if prod.delivery_type == "activation":
                reseller_status = BatStoreService.get_order_reseller_status(placed)
                order_status = "completed" if reseller_status == "completed" else "pending_fulfillment"
        except Exception as e:
            logging.error("Admin manual-sale placement error for product #%s: %s", product_id, e)
            return JSONResponse({"error": f"supplier_failed: {str(e)[:100]}"}, status_code=502)

        order_details = [{
            "product_id": prod.product_id,
            "name": prod.name,
            "quantity": qty,
            "cost_usd": prod.cost_usd,
            "sell_usd": total,
            "delivery_type": prod.delivery_type,
            "delivery_goods": goods_list,
            "warranty_days": prod.warranty_days or 0,
            "externally_paid": True,
            "recorded_by": admin_tg_id,
        }]

        order = await BatStoreOrderRepository.create(BatStoreOrderDTO(
            telegram_id=target_tg_id,
            total_sell=total,
            status=order_status,
            customer_reference=cust_ref,
            external_order_ref=str(external_ref) if external_ref else None,
            details=order_details
        ), session)
        session.add(AdminAuditLog(
            admin_tg_id=admin_tg_id,
            action="manual_sale",
            details={
                "order_id": order.id,
                "target_tg_id": target_tg_id,
                "product_id": product_id,
                "quantity": qty,
                "revenue_usd": total,
                "cost_usd": float(prod.cost_usd or 0.0) * qty,
            }
        ))
        await session_commit(session)
        invalidate_admin_stats_cache()

        sym = config.CURRENCY.get_localized_symbol()
        from bot import bot
        try:
            await bot.send_message(
                chat_id=target_tg_id,
                text=(
                    f"🛍️ <b>تم تسجيل طلبك من قبل إدارة المتجر:</b>\n\n"
                    f"• الطلب: #{order.id}\n"
                    f"• المنتج: {prod.name} ({qty}×)\n"
                    f"• القيمة: {total:.2f}{sym} (مدفوع خارج الرصيد)\n"
                    f"• الحالة: {order_status}\n\n"
                    + ("بيانات التسليم:\n" + "\n".join(f"• <code>{g}</code>" for g in goods_list) if goods_list else "جاري تجهيز الطلب.")
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    return {
        "status": "success",
        "order_id": order.id,
        "product_name": prod.name,
        "quantity": qty,
        "revenue_usd": total,
        "target_tg_id": target_tg_id,
        "goods": goods_list,
        "order_status": order_status,
    }


@router.post("/api/admin/free-order")
async def admin_free_order(request: Request):
    """Retired zero-price gift route: manual sales are paid externally now."""
    return JSONResponse({"error": "manual_sale_required"}, status_code=410)


@router.post("/api/admin/warranty/replace")
async def admin_dispatch_warranty_replacement(request: Request):
    """Admin 1-click warranty replacement dispatch."""
    from bot import bot
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    order_id = int(body.get("order_id") or 0)
    if not order_id:
        return JSONResponse({"error": "missing_order_id"}, status_code=400)

    async with get_db_session() as session:
        order = await BatStoreOrderRepository.get_by_id(order_id, session)
        if not order:
            return JSONResponse({"error": "order_not_found"}, status_code=404)

        details = order.details or []
        pid = details[0].get("product_id") if details else None
        pname = details[0].get("name") if details else "Product"
        if not pid:
            return JSONResponse({"error": "missing_product_info"}, status_code=400)

        repl_ref = f"admin-warranty-{order.id}-{uuid.uuid4().hex[:6]}"
        try:
            placed = await BatStoreService.place_order(
                session, pid, 1,
                customer_reference=repl_ref,
                idempotency_key=repl_ref,
            )
            items = placed.get("order", {}).get("items") or []
            goods_list = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
        except Exception as e:
            logging.error("Admin warranty replacement failed for order #%s: %s", order_id, e)
            return JSONResponse({"error": f"فشل المورد في توفير البديل: {str(e)[:100]}"}, status_code=502)

        order.warranty_claimed = True
        order.warranty_claimed_at = datetime.datetime.now(datetime.timezone.utc)
        details.append({
            "replacement": True,
            "product_id": pid,
            "name": f"{pname} (Warranty Replacement)",
            "delivery_goods": goods_list,
            "dispatched_by": admin_id,
            "dispatched_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })
        order.details = details
        await BatStoreOrderRepository.update(order, session)
        await session_commit(session)

        if goods_list:
            try:
                cred_lines = "\n".join(f"• <code>{g}</code>" for g in goods_list)
                msg = (
                    f"🛡️ <b>تم اعتماد طلب الضمان وإصدار بديل جديد!</b>\n\n"
                    f"طلبك رقم: #{order.id}\n"
                    f"المنتج: {pname}\n\n"
                    f"<b>البيانات البديلة المستلمة:</b>\n{cred_lines}\n\n"
                    f"شكراً لصبرك ونتمنى لك تجربة ممتعة! ✨"
                )
                await bot.send_message(chat_id=order.telegram_id, text=msg, parse_mode="HTML")
            except Exception as e:
                logging.warning("Could not send warranty replacement DM to user %s: %s", order.telegram_id, e)

        return {
            "status": "success",
            "order_id": order.id,
            "goods": goods_list
        }


@router.get("/api/admin/reports/export")
async def admin_export_accounting_ledger(request: Request, tg_id: int, start_date: str = "", end_date: str = ""):
    """Export accounting CSV ledger of orders and gross profit for reconciliation."""
    if not verify_admin(tg_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    now = datetime.datetime.now(datetime.timezone.utc)
    since = now - datetime.timedelta(days=30)
    until = now + datetime.timedelta(days=1)

    if start_date:
        try:
            since = datetime.datetime.fromisoformat(start_date).replace(tzinfo=datetime.timezone.utc)
        except Exception:
            pass
    if end_date:
        try:
            until = datetime.datetime.fromisoformat(end_date).replace(tzinfo=datetime.timezone.utc)
        except Exception:
            pass

    async with get_db_session() as session:
        stmt = (
            select(BatStoreOrder, User.telegram_username)
            .outerjoin(User, User.telegram_id == BatStoreOrder.telegram_id)
            .where(BatStoreOrder.created_at >= since, BatStoreOrder.created_at <= until)
            .order_by(BatStoreOrder.id.asc())
        )
        rows = (await session_execute(stmt, session)).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Order ID", "Date UTC", "Telegram ID", "Username", "Status",
            "Product Names", "Quantity", "Revenue USD", "Wholesale Cost USD",
            "Gross Profit USD", "Payment Method", "External Ref"
        ])

        for o, uname in rows:
            items_names = "; ".join(d.get("name") or "Product" for d in (o.details or []))
            total_qty = sum(int(d.get("quantity") or 1) for d in (o.details or []))
            cost = float(order_cost(o.details))
            sell = float(o.total_sell or 0.0)
            profit = round(sell - cost, 2)
            method = "external" if externally_paid(o) else "store_balance"
            date_str = o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else ""

            writer.writerow([
                o.id, date_str, o.telegram_id, f"@{uname}" if uname else "", o.status,
                items_names, total_qty, f"{sell:.2f}", f"{cost:.2f}",
                f"{profit:.2f}", method, o.external_order_ref or ""
            ])

        csv_data = output.getvalue()
        filename = f"ghstore_ledger_{since.strftime('%Y%m%d')}_{until.strftime('%Y%m%d')}.csv"
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@router.post("/api/admin/flash-sale/update")
async def admin_update_flash_sale(request: Request):
    """Admin updates store flash sale status and countdown duration."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    enabled = "true" if body.get("enabled") else "false"
    pct = str(float(body.get("percent") or 15.0))
    duration_hours = int(body.get("duration_hours") or 24)
    end_ts = str(int(time.time()) + (duration_hours * 3600)) if enabled == "true" else "0"
    async with get_db_session() as session:
        await ConfigService.set(session, "FLASH_SALE_ENABLED", enabled)
        await ConfigService.set(session, "FLASH_SALE_PERCENT", pct)
        await ConfigService.set(session, "FLASH_SALE_END_TIMESTAMP", end_ts)
        await session_commit(session)
    invalidate_catalog_cache()
    return {"status": "ok", "enabled": enabled == "true", "end_timestamp": int(end_ts)}


@router.post("/api/admin/broadcast")
async def admin_start_broadcast(request: Request):
    """Admin starts an asynchronous rate-limited Telegram broadcast."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    msg = str(body.get("message") or "").strip()
    segment = str(body.get("target_segment") or "all").strip().lower()
    if not msg:
        return JSONResponse({"error": "empty_message"}, status_code=400)

    broadcast_id = uuid.uuid4().hex[:8]
    asyncio.create_task(_run_admin_broadcast(broadcast_id, msg, segment))
    return {"status": "started", "broadcast_id": broadcast_id}


@router.get("/api/admin/broadcast/status")
async def admin_broadcast_status(request: Request, tg_id: int, broadcast_id: str):
    """Check live status and delivery metrics of an active broadcast."""
    from bot import redis
    if not verify_admin(tg_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    try:
        if redis:
            raw = await redis.get(f"ghstore:broadcast:{broadcast_id}")
            if raw:
                return json.loads(raw)
    except Exception:
        pass
    return {"active": False, "sent": 0, "total": 0, "failed": 0}


@router.post("/api/admin/rate/update")
async def admin_update_rate(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    rate_raw = float(body.get("syp_rate") or 0.0)
    if rate_raw <= 0:
        return JSONResponse({"error": "invalid_rate"}, status_code=400)
    stored_rate = str(1.0 / rate_raw) if rate_raw > 100.0 else str(rate_raw)
    async with get_db_session() as session:
        await ConfigService.set(session, "SAM_SYP_USD_RATE", stored_rate)
        await session_commit(session)
    return {"status": "ok", "syp_rate": int(round(rate_raw if rate_raw > 100.0 else 1.0 / rate_raw))}


@router.post("/api/admin/referral-rate/update")
async def admin_update_referral_rate(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    ref_rate = float(body.get("referral_rate") or 0.2)
    async with get_db_session() as session:
        await ConfigService.set(session, "REFERRAL_MARGIN_COMMISSION_PERCENT", str(ref_rate))
        await session_commit(session)
    return {"status": "ok", "referral_rate": ref_rate}


@router.post("/api/admin/store-logo/update")
async def admin_update_store_logo(request: Request):
    """Update the store logo URL in PostgreSQL app_config."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    url = (body.get("store_logo_url") or "").strip()
    async with get_db_session() as session:
        await ConfigService.set(session, "STORE_LOGO_URL", url)
        await session_commit(session)
    invalidate_catalog_cache()
    return {"status": "ok", "store_logo_url": url}


@router.post("/api/admin/margin/update")
async def admin_update_margin(request: Request):
    """Update global profit margin percentage on reseller products."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    margin = float(body.get("margin_percent") or 20.0)
    async with get_db_session() as session:
        await ConfigService.set(session, "MARGIN_PERCENT", str(margin))
        await session_commit(session)
    invalidate_catalog_cache()
    return {"status": "ok", "margin_percent": margin}


@router.post("/api/admin/stars-rate/update")
async def admin_update_stars_rate(request: Request):
    """Update Telegram Stars to USD conversion rate."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    rate = float(body.get("stars_rate") or 0.01)
    async with get_db_session() as session:
        await ConfigService.set(session, "GHSTORE_STARS_TO_USD", str(rate))
        await session_commit(session)
    return {"status": "ok", "stars_rate": rate}


@router.post("/api/admin/announcement/update")
async def admin_update_announcement(request: Request):
    """Update broadcast store announcement message."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    announcement = (body.get("announcement") or "").strip()
    async with get_db_session() as session:
        await ConfigService.set(session, "STORE_ANNOUNCEMENT", announcement)
        await session_commit(session)
    return {"status": "ok", "announcement": announcement}

@router.post("/api/admin/trending-tags/update")
async def admin_update_trending_tags(request: Request):
    """Update admin-configured trending search tags."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    tags = (body.get("tags") or "").strip()
    async with get_db_session() as session:
        await ConfigService.set(session, "STORE_TRENDING_TAGS", tags)
        await session_commit(session)
    return {"status": "ok", "tags": tags}


@router.post("/api/admin/catalog/sync")
async def admin_sync_catalog(request: Request):
    """Force an immediate background sync of the BatStore supplier catalog."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        created, updated = await BatStoreService.sync_catalog(session)
        await session_commit(session)
    invalidate_catalog_cache()
    return {
        "status": "ok",
        "created": created,
        "updated": updated,
        "synced_at": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    }


@router.post("/api/admin/autorefund/toggle")
async def admin_toggle_autorefund(request: Request):
    """Toggle automated refund mode (enabled vs manual)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        curr = await ConfigService.get(session, "AUTOREFUND_ENABLED", default="false")
        new_val = "false" if curr == "true" else "true"
        await ConfigService.set(session, "AUTOREFUND_ENABLED", new_val)
        await session_commit(session)
    return {"status": "ok", "autorefund_enabled": new_val == "true"}


@router.get("/api/admin/stuck-orders")
async def admin_get_stuck_orders(tg_id: int):
    """Return orders that are pending fulfillment or stuck requiring admin action."""
    if not verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        stmt = select(BatStoreOrder).where(
            BatStoreOrder.status.in_(["pending_fulfillment", "pending"])
        ).order_by(BatStoreOrder.id.desc()).limit(50)
        rows = (await session_execute(stmt, session)).scalars().all()

        stuck_list = []
        sym = config.CURRENCY.get_localized_symbol()
        for o in rows:
            user = await UserRepository.get_by_tgid(o.telegram_id, session)
            product_names = []
            for d in (o.details or []):
                product_names.append(d.get("name") or "Product")

            stuck_list.append({
                "id": o.id,
                "telegram_id": o.telegram_id,
                "username": user.telegram_username if user else "",
                "products": ", ".join(product_names) if product_names else "Order",
                "total_sell": round(float(o.total_sell or 0.0), 2),
                "sym": sym,
                "status": o.status,
                "created_at": o.created_at.strftime("%b %d, %H:%M") if o.created_at else "",
                "customer_reference": o.customer_reference or "",
            })
    return {"stuck_orders": stuck_list}


@router.get("/api/admin/live-activity")
async def admin_get_live_activity(tg_id: int, limit: int = 50):
    """Real-time store activity radar for admin: live stream of all customer orders & recharges."""
    if not verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    async with get_db_session() as session:
        activities = []
        sym = config.CURRENCY.get_localized_symbol()

        # 1. Orders
        stmt_orders = select(BatStoreOrder).order_by(BatStoreOrder.id.desc()).limit(limit)
        orders = (await session_execute(stmt_orders, session)).scalars().all()
        for o in orders:
            product_names = []
            for d in (o.details or []):
                product_names.append(d.get("name") or "Product")
            activities.append({
                "id": f"order_{o.id}",
                "raw_id": o.id,
                "type": "order",
                "title": ", ".join(product_names) if product_names else "طلب منتج",
                "telegram_id": o.telegram_id,
                "total_usd": round(float(o.total_sell or 0.0), 2),
                "sym": sym,
                "status": o.status,
                "needs_attention": o.status in ("pending_fulfillment", "failed", "pending"),
                "created_at": o.created_at.strftime("%b %d, %H:%M") if getattr(o, "created_at", None) else "",
                "timestamp": o.created_at.timestamp() if getattr(o, "created_at", None) else 0,
            })

        # 2. SAM Recharges
        stmt_sam = select(SamPayment).order_by(SamPayment.id.desc()).limit(limit)
        sam_rows = (await session_execute(stmt_sam, session)).scalars().all()
        for sp in sam_rows:
            is_paid = (sp.event == "invoice.paid")
            is_expired = (sp.event == "invoice.expired")
            status_label = "completed" if is_paid else ("failed" if is_expired else "pending")
            activities.append({
                "id": f"sam_{sp.id}",
                "raw_id": sp.id,
                "type": "recharge",
                "method": sp.payment_method or "shamcash",
                "title": f"شحن {sp.payment_method.upper() if sp.payment_method else 'SAM'}",
                "telegram_id": sp.telegram_id,
                "amount_usd": round(float(sp.usd_amount or 0.0), 2),
                "local_amount": round(float(sp.amount or 0.0), 2),
                "currency": sp.currency or "USD",
                "invoice_id": sp.invoice_id or "",
                "status": status_label,
                "needs_attention": not is_paid,
                "created_at": sp.created_at.strftime("%b %d, %H:%M") if getattr(sp, "created_at", None) else "",
                "timestamp": sp.created_at.timestamp() if getattr(sp, "created_at", None) else 0,
            })

        # 3. Stars Recharges
        stmt_stars = select(StarsPayment).order_by(StarsPayment.id.desc()).limit(limit)
        stars_rows = (await session_execute(stmt_stars, session)).scalars().all()
        for stp in stars_rows:
            activities.append({
                "id": f"stars_{stp.id}",
                "raw_id": stp.id,
                "type": "recharge",
                "method": "stars",
                "title": "شحن نجوم تيليجرام (Stars)",
                "telegram_id": stp.telegram_id,
                "amount_usd": round(float(stp.usd_amount or 0.0), 2),
                "local_amount": float(stp.stars_amount or 0.0),
                "currency": "XTR",
                "invoice_id": stp.telegram_payment_charge_id or "",
                "status": "completed",
                "needs_attention": False,
                "created_at": stp.created_at.strftime("%b %d, %H:%M") if getattr(stp, "created_at", None) else "",
                "timestamp": stp.created_at.timestamp() if getattr(stp, "created_at", None) else 0,
            })

        activities.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        user_tg_ids = {a["telegram_id"] for a in activities if a.get("telegram_id")}
        if user_tg_ids:
            u_stmt = select(User.telegram_id, User.telegram_username).where(User.telegram_id.in_(user_tg_ids))
            user_map = {row[0]: (row[1] or "") for row in (await session_execute(u_stmt, session)).all()}
            for a in activities:
                a["username"] = user_map.get(a["telegram_id"], "")

        needs_attention_count = sum(1 for a in activities if a.get("needs_attention"))

        return {
            "status": "ok",
            "count": len(activities),
            "needs_attention_count": needs_attention_count,
            "activities": activities[:limit]
        }


@router.post("/api/admin/recharge/approve")
async def admin_approve_recharge(request: Request):
    """Admin manually approves a failed or pending recharge, credits customer balance, and sends Telegram alert."""
    from bot import bot
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_tg_id = int(body.get("admin_tg_id") or 0)
    if not verify_admin(admin_tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    recharge_id = str(body.get("recharge_id") or "")
    target_tg_id = int(body.get("telegram_id") or 0)
    amount_usd = float(body.get("amount_usd") or 0.0)
    async with get_db_session() as session:
        if not target_tg_id and recharge_id.startswith("sam_"):
            try:
                raw_sam_id = int(recharge_id.replace("sam_", ""))
                sp_check = (await session_execute(select(SamPayment).where(SamPayment.id == raw_sam_id), session)).scalar_one_or_none()
                if sp_check:
                    target_tg_id = sp_check.telegram_id
                    if amount_usd <= 0:
                        amount_usd = float(sp_check.usd_amount or 0.0)
            except Exception:
                pass

        if not target_tg_id or amount_usd <= 0:
            return JSONResponse({"error": "invalid_params"}, status_code=400)

        res = await session_execute(
            select(User.top_up_amount, User.consume_records).where(User.telegram_id == target_tg_id)
        )
        user_row = res.first()
        if not user_row:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        user = await UserRepository.get_by_tgid(target_tg_id, session)
        user.top_up_amount = float(user.top_up_amount or 0.0) + amount_usd
        await UserRepository.update(user, session)
        new_balance = round(float(user.top_up_amount or 0.0) - float(user.consume_records or 0.0), 2)

        if recharge_id.startswith("sam_"):
            raw_sam_id = int(recharge_id.replace("sam_", ""))
            sp = (await session_execute(select(SamPayment).where(SamPayment.id == raw_sam_id), session)).scalar_one_or_none()
            if sp:
                sp.event = "invoice.paid"

        session.add(AdminAuditLog(
            admin_tg_id=admin_tg_id,
            action="recharge_approved",
            details={"target_user": target_tg_id, "amount_usd": amount_usd, "recharge_id": recharge_id}
        ))
        await session_commit(session)
        invalidate_admin_stats_cache()

        try:
            msg = (
                f"✅ <b>تم اعتماد عملية شحن رصيدك بنجاح!</b>\n\n"
                f"تمت مراجعة العملية واعتمادها من قبل إدارة المتجر.\n"
                f"💰 <b>المبلغ المضاف:</b> +${amount_usd:.2f} USD\n"
                f"🛍️ رصيدك الحالي جاهز للتسوق والاستخدام الفوري داخل المتجر!\n\n"
                f"شكراً لصبرك وتسوقك معنا في GH Store! ✨"
            )
            await bot.send_message(chat_id=target_tg_id, text=msg, parse_mode="HTML")
        except Exception as e:
            logging.warning("Could not send recharge approval DM to %s: %s", target_tg_id, e)

        return {
            "status": "ok",
            "credited_amount": amount_usd,
            "target_tg_id": target_tg_id,
            "new_balance": new_balance
        }


@router.post("/api/admin/stuck-orders/refund")
async def admin_refund_stuck_order(request: Request):
    """Admin manually refunds a stuck order, crediting user balance and notifying them."""
    from bot import bot
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    order_id = int(body.get("order_id") or 0)
    if not order_id:
        return JSONResponse({"error": "missing_order_id"}, status_code=400)

    async with get_db_session() as session:
        order = await BatStoreOrderRepository.get_by_id(order_id, session)
        if not order:
            return JSONResponse({"error": "order_not_found"}, status_code=404)
        if order.status == "refunded":
            return JSONResponse({"error": "already_refunded"}, status_code=400)

        refund_amount = round(float(order.total_sell or 0.0), 2)
        wallet_credited = False
        user = await UserRepository.get_by_tgid(order.telegram_id, session)
        stars_refunded = False
        # Check if paid via Telegram Stars
        cust_ref = order.customer_reference or ""
        if cust_ref.startswith("stars-") or "stars" in (order.external_order_ref or ""):
            from repositories.stars_payment import StarsPaymentRepository
            stmt_stars = select(StarsPayment).where(StarsPayment.telegram_id == order.telegram_id).order_by(StarsPayment.id.desc()).limit(1)
            sp = (await session_execute(stmt_stars, session)).scalar_one_or_none()
            if sp and sp.telegram_payment_charge_id:
                try:
                    await bot.refund_star_payment(
                        user_id=order.telegram_id,
                        telegram_payment_charge_id=sp.telegram_payment_charge_id
                    )
                    stars_refunded = True
                    await bot.send_message(
                        order.telegram_id,
                        f"⭐ <b>تم استرداد دفع نجوم تيليجرام (Stars) بنجاح!</b>\n\nتم إرجاع النجوم لطلبك #{order.id} مباشرة إلى محفظة نجوم تيليجرام الخاصة بك."
                    )
                except Exception as e:
                    logging.warning("Failed to refund star payment via Bot API: %s", e)

        if not stars_refunded and user and not externally_paid(order):
            user.top_up_amount = (user.top_up_amount or 0.0) + refund_amount
            await UserRepository.update(user, session)
            wallet_credited = True
            try:
                sym = config.CURRENCY.get_localized_symbol()
                await bot.send_message(
                    order.telegram_id,
                    f"💸 <b>إشعار استرداد مالي من إدارة المتجر:</b>\n\n"
                    f"تم استرداد مبلغ <b>${refund_amount:.2f}{sym}</b> لطلبك #{order.id} بنجاح إلى رصيدك المتاح."
                )
            except Exception:
                pass
        order.status = "refunded"
        await BatStoreOrderRepository.update(order, session)
        await session_commit(session)
        invalidate_admin_stats_cache()

    return {"status": "ok", "refunded_amount": refund_amount if wallet_credited else 0.0, "order_id": order_id, "wallet_credited": wallet_credited}


@router.post("/api/admin/prodseller/test-balance")
async def admin_test_prodseller_balance(request: Request):
    """Test ProdSeller API key live and return real-time balance and membership tier."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    api_key = str(body.get("api_key") or "").strip()
    try:
        async with get_db_session() as session:
            if api_key:
                headers = {"X-API-Key": api_key, "Accept": "application/json"}
                async with await ProdSellerService._client() as client:
                    resp = await client.get(f"{ProdSellerService.BASE_URL}/balance", headers=headers)
                if resp.status_code != 200:
                    return JSONResponse({"error": f"ProdSeller HTTP {resp.status_code}: {resp.text[:100]}"}, status_code=400)
                data = resp.json()
            else:
                data = await ProdSellerService.get_balance(session)
        return {
            "status": "ok",
            "balance": float(data.get("balance") or 0.0),
            "membership": str(data.get("membership") or "bronze"),
            "username": str(data.get("username") or ""),
            "telegram_id": data.get("telegramId"),
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@router.post("/api/admin/batstore/test-balance")
async def admin_test_batstore_balance(request: Request):
    """Test BatStore API key live and return real-time balance and user status."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    api_key = str(body.get("api_key") or "").strip()
    try:
        async with get_db_session() as session:
            if api_key:
                base = config.BATSTORE_API_URL or "https://api.reseller.ventebot.com"
                headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
                async with await BatStoreService._client() as client:
                    resp = await client.get(f"{base}/user", headers=headers)
                if resp.status_code != 200:
                    return JSONResponse({"error": f"BatStore HTTP {resp.status_code}: {resp.text[:100]}"}, status_code=400)
                data = resp.json()
            else:
                data = await BatStoreService.me(session)
        raw_b = data.get("wallet_balance")
        if raw_b is None:
            raw_b = data.get("wallet", {}).get("balance", 0.0)
        return {
            "status": "ok",
            "balance": round(float(raw_b or 0.0), 2),
            "username": data.get("username") or data.get("name") or "",
            "role": data.get("role") or "reseller"
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@router.get("/api/admin/supplier/details")
async def admin_get_supplier_details(tg_id: int):
    """Return paired supplier settings, status, and config for the dedicated admin suppliers page."""
    if not verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        bat_key = await ConfigService.get(session, "BATSTORE_API_KEY", env_fallback=os.environ.get("BATSTORE_API_KEY", ""))
        prod_key = await ConfigService.get(session, "PRODSELLER_API_KEY", env_fallback=os.environ.get("PRODSELLER_API_KEY", ""))
        strategy = await ConfigService.get(session, "SUPPLIER_ROUTING_STRATEGY", default="auto_cheapest")
        bat_sync = (await ConfigService.get(session, "BATSTORE_SYNC_ENABLED", default="true")).lower() == "true"
        prod_sync = (await ConfigService.get(session, "PRODSELLER_SYNC_ENABLED", default="true")).lower() == "true"
        auto_failover = (await ConfigService.get(session, "SUPPLIER_AUTO_FAILOVER", default="true")).lower() == "true"

        bat_prod_count = (await session_execute(select(func.count(BatStoreProduct.id)).where(BatStoreProduct.supplier == "batstore"), session)).scalar() or 0
        prod_prod_count = (await session_execute(select(func.count(BatStoreProduct.id)).where(BatStoreProduct.supplier == "prodseller"), session)).scalar() or 0

    return {
        "batstore": {
            "name": "سيرفر 1: BatStore / VenteBot",
            "badge": "سيرفر 1 (BatStore)",
            "api_url": config.BATSTORE_API_URL or "https://api.reseller.ventebot.com",
            "api_key_configured": bool(bat_key),
            "api_key_masked": (bat_key[:6] + "..." + bat_key[-4:]) if len(bat_key or "") > 10 else ("configured" if bat_key else ""),
            "sync_enabled": bat_sync,
            "product_count": bat_prod_count,
        },
        "prodseller": {
            "name": "سيرفر 2: ProdSeller",
            "badge": "سيرفر 2 (ProdSeller)",
            "api_url": "https://prodseller.com/v1",
            "api_key_configured": bool(prod_key),
            "api_key_masked": (prod_key[:6] + "..." + prod_key[-4:]) if len(prod_key or "") > 10 else ("configured" if prod_key else ""),
            "sync_enabled": prod_sync,
            "product_count": prod_prod_count,
        },
        "routing_strategy": strategy,
        "auto_failover": auto_failover,
    }


@router.post("/api/admin/supplier/config")
async def admin_update_supplier_config(request: Request):
    """Save paired supplier keys, sync preferences, and routing strategy to database."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    bat_key = str(body.get("batstore_api_key") or "").strip()
    prod_key = str(body.get("prodseller_api_key") or "").strip()
    strategy = str(body.get("routing_strategy") or "auto_cheapest").strip().lower()
    bat_sync = body.get("batstore_sync_enabled")
    prod_sync = body.get("prodseller_sync_enabled")
    failover = body.get("auto_failover")

    async with get_db_session() as session:
        if bat_key:
            await ConfigService.set(session, "BATSTORE_API_KEY", bat_key)
        if prod_key:
            await ConfigService.set(session, "PRODSELLER_API_KEY", prod_key)
        if strategy in ("auto_cheapest", "batstore_primary", "prodseller_primary"):
            await ConfigService.set(session, "SUPPLIER_ROUTING_STRATEGY", strategy)
        if bat_sync is not None:
            await ConfigService.set(session, "BATSTORE_SYNC_ENABLED", "true" if bat_sync else "false")
        if prod_sync is not None:
            await ConfigService.set(session, "PRODSELLER_SYNC_ENABLED", "true" if prod_sync else "false")
        if failover is not None:
            await ConfigService.set(session, "SUPPLIER_AUTO_FAILOVER", "true" if failover else "false")
        await session_commit(session)

    return {"status": "ok", "routing_strategy": strategy}


@router.post("/api/admin/supplier/sync")
async def admin_sync_all_suppliers(request: Request):
    """Trigger manual 1-tap catalog synchronization across all suppliers."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    async with get_db_session() as session:
        res = await MultiSupplierService.sync_all_suppliers(session)
    invalidate_catalog_cache()
    return {"status": "ok", "result": res}


@router.get("/api/admin/config/all")
async def admin_get_all_configs(tg_id: int):
    """Return all system configuration keys, current values, and descriptions."""
    if not verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        configs_list = []
        for key, meta in CONFIG_DEFINITIONS.items():
            if key == "SAM_CURRENCY":
                continue
            val = await ConfigService.get(session, key, env_fallback=os.environ.get(key, ""))
            is_secret = meta.get("secret", False)
            configs_list.append({
                "key": key,
                "desc": meta.get("desc", ""),
                "secret": is_secret,
                "value": val or "",
            })
        custom_keys = ["STORE_LOGO_URL", "STORE_ANNOUNCEMENT", "GLOBAL_MARGIN_PERCENT", "AUTOREFUND_ENABLED", "WEBHOOK_HOST"]
        for ck in custom_keys:
            if not any(c["key"] == ck for c in configs_list):
                val = await ConfigService.get(session, ck, env_fallback=os.environ.get(ck, ""))
                configs_list.append({
                    "key": ck,
                    "desc": f"System setting {ck}",
                    "secret": False,
                    "value": val or "",
                })
    return {"configs": configs_list}


@router.post("/api/admin/config/set")
async def admin_set_config(request: Request):
    """Update any system configuration key in PostgreSQL app_config."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    key = str(body.get("key") or "").strip()
    value = str(body.get("value") or "").strip()
    if not key:
        return JSONResponse({"error": "missing_key"}, status_code=400)
    async with get_db_session() as session:
        await ConfigService.set(session, key, value)
        await session_commit(session)
    return {"status": "ok", "key": key, "value": value}


@router.get("/api/admin/users")
async def admin_get_users(tg_id: int, query: str = ""):
    if not verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        stmt = select(User)
        q = (query or "").strip().lower()
        if q:
            if q.isdigit():
                stmt = stmt.where((User.telegram_id == int(q)) | (User.id == int(q)))
            else:
                uname = q.lstrip("@")
                stmt = stmt.where(User.telegram_username.ilike(f"%{uname}%"))
        else:
            stmt = stmt.order_by(User.id.desc()).limit(25)
        rows = await session_execute(stmt, session)
        users = rows.scalars().all()
        result = []
        from services.user import get_vip_tier_info
        for u in users:
            bal = round((u.top_up_amount or 0.0) - (u.consume_records or 0.0), 2)
            tier_label, disc_pct = get_vip_tier_info(u.consume_records, getattr(u, "custom_discount_pct", None))
            ref_qty = await UserRepository.get_referrals_qty_by_referrer_id(u.id, session)
            result.append({
                "id": u.id,
                "telegram_id": u.telegram_id,
                "username": u.telegram_username or "",
                "balance": bal,
                "total_spent": round(u.consume_records or 0.0, 2),
                "vip_tier": tier_label,
                "vip_discount": disc_pct,
                "is_banned": bool(u.is_banned),
                "referrals_count": ref_qty,
                "custom_discount_pct": getattr(u, "custom_discount_pct", None),
                "registered_at": u.registered_at.strftime("%Y-%m-%d") if getattr(u, "registered_at", None) else ""
            })
    return {"users": result}


@router.post("/api/admin/users/adjust-balance")
async def admin_adjust_balance(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    target_tg_id = int(body.get("target_tg_id") or 0)
    amount = float(body.get("amount") or 0.0)
    action_type = body.get("action", "add")
    if not target_tg_id or amount <= 0:
        return JSONResponse({"error": "invalid_params"}, status_code=400)
    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(target_tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)
        if action_type == "add":
            user.top_up_amount = (user.top_up_amount or 0.0) + amount
        elif action_type == "set":
            user.top_up_amount = amount
            user.consume_records = 0.0
        elif action_type == "deduct":
            user.consume_records = (user.consume_records or 0.0) + amount
        await UserRepository.update(user, session)
        audit_log = AdminAuditLog(
            admin_tg_id=admin_id,
            action="adjust_balance",
            details={"target_user": target_tg_id, "amount": amount, "action_type": action_type}
        )
        session.add(audit_log)
        await session_commit(session)
        invalidate_admin_stats_cache()
        new_bal = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
        audit_id = audit_log.id
    return {"status": "ok", "new_balance": new_bal, "audit_id": audit_id}


@router.post("/api/admin/audit/rollback")
async def admin_audit_rollback(request: Request):
    """Reverses a previous balance adjustment logged in AdminAuditLog."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    log_id = int(body.get("audit_id") or 0)
    if not log_id:
        return JSONResponse({"error": "missing_audit_id"}, status_code=400)

    async with get_db_session() as session:
        stmt = select(AdminAuditLog).where(AdminAuditLog.id == log_id)
        audit_entry = (await session_execute(stmt, session)).scalar_one_or_none()
        if not audit_entry:
            return JSONResponse({"error": "audit_not_found"}, status_code=404)

        if audit_entry.action != "adjust_balance":
            return JSONResponse({"error": "action_cannot_be_rolled_back"}, status_code=400)

        details = audit_entry.details or {}
        target_tg_id = int(details.get("target_user") or 0)
        amount = float(details.get("amount") or 0.0)
        action_type = details.get("action_type")

        if not target_tg_id or amount <= 0:
            return JSONResponse({"error": "invalid_audit_details"}, status_code=400)

        user = await UserRepository.get_by_tgid(target_tg_id, session)
        if not user:
            return JSONResponse({"error": "target_user_not_found"}, status_code=404)

        if action_type == "add":
            user.top_up_amount = max(0.0, (user.top_up_amount or 0.0) - amount)
        elif action_type == "deduct":
            user.consume_records = max(0.0, (user.consume_records or 0.0) - amount)
        else:
            return JSONResponse({"error": "set_cannot_be_automatically_reversed"}, status_code=400)

        await UserRepository.update(user, session)
        session.add(AdminAuditLog(
            admin_tg_id=admin_id,
            action="rollback_adjust_balance",
            details={"original_audit_id": log_id, "target_user": target_tg_id, "amount": amount, "reversed_action": action_type}
        ))
        await session_commit(session)
        invalidate_admin_stats_cache()
        new_bal = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)

    return {"status": "ok", "message": "rolled_back", "target_user": target_tg_id, "new_balance": new_bal}

@router.post("/api/admin/users/toggle-ban")
async def admin_toggle_ban(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    target_tg_id = int(body.get("target_tg_id") or 0)
    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(target_tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)
        user.is_banned = not user.is_banned
        await UserRepository.update(user, session)
        await session_commit(session)
    return {"status": "ok", "is_banned": user.is_banned}


@router.post("/api/admin/users/send-message")
async def admin_send_user_message(request: Request):
    """Admin sends direct message to a customer from the bot."""
    from bot import bot
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    target_tg_id = int(body.get("target_tg_id") or 0)
    msg = str(body.get("message") or "").strip()
    if not target_tg_id or not msg:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    try:
        await bot.send_message(chat_id=target_tg_id, text=msg, parse_mode="HTML")
        return {"status": "ok", "target_tg_id": target_tg_id}
    except Exception as e:
        return JSONResponse({"error": f"Failed to send: {str(e)}"}, status_code=500)


@router.post("/api/admin/users/set-discount")
async def admin_set_discount(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    target_tg_id = int(body.get("target_tg_id") or 0)
    disc = body.get("discount_pct")
    disc_val = float(disc) if (disc is not None and disc != "") else None
    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(target_tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)
        user.custom_discount_pct = disc_val
        await UserRepository.update(user, session)
        await session_commit(session)
    return {"status": "ok", "custom_discount_pct": disc_val}


@router.get("/api/admin/orders")
async def admin_get_orders(tg_id: int, status: str = "all"):
    if not verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        stmt = select(BatStoreOrder)
        if status != "all":
            stmt = stmt.where(BatStoreOrder.status == status)
        stmt = stmt.order_by(BatStoreOrder.id.desc()).limit(30)
        rows = await session_execute(stmt, session)
        orders = rows.scalars().all()
        result = []
        for o in orders:
            p_names = [d.get("name") or "Product" for d in (o.details or [])]
            cost_tot = sum(float(d.get("cost_usd") or 0.0) * int(d.get("quantity") or 1) for d in (o.details or []))
            sell_tot = float(o.total_sell or 0.0)
            profit = round(sell_tot - cost_tot, 2)
            result.append({
                "id": o.id,
                "telegram_id": o.telegram_id,
                "total_sell": sell_tot,
                "cost_usd": round(cost_tot, 2),
                "profit_usd": profit,
                "status": o.status,
                "products": ", ".join(p_names) if p_names else "Order",
                "customer_reference": o.customer_reference or "",
                "created_at": o.created_at.strftime("%Y-%m-%d %H:%M") if getattr(o, "created_at", None) else "",
            })
    return {"orders": result}


@router.post("/api/admin/orders/update-status")
async def admin_update_order_status(request: Request):
    from bot import bot
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    order_id = int(body.get("order_id") or 0)
    new_status = str(body.get("status") or "").strip()
    if not order_id or not new_status:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)
    async with get_db_session() as session:
        order = await BatStoreOrderRepository.get_by_id(order_id, session)
        if not order:
            return JSONResponse({"error": "order_not_found"}, status_code=404)
        order.status = new_status
        await BatStoreOrderRepository.update(order, session)

        if new_status == "refunded":
            user = await UserRepository.get_by_tgid(order.telegram_id, session)
            if user:
                user.top_up_amount = (user.top_up_amount or 0.0) + (order.total_sell or 0.0)
                await UserRepository.update(user, session)
                try:
                    await bot.send_message(order.telegram_id, f"💸 تم استرداد مبلغ ${order.total_sell:.2f} لطلبك #{order.id} بنجاح.")
                except Exception:
                    pass

        await session_commit(session)
        invalidate_admin_stats_cache()
    return {"status": "ok", "order_id": order_id, "new_status": new_status}


@router.get("/api/admin/coupons")
async def admin_get_coupons(tg_id: int):
    if not verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        stmt = select(Coupon).order_by(Coupon.id.desc()).limit(30)
        rows = await session_execute(stmt, session)
        coupons = rows.scalars().all()
        result = []
        for c in coupons:
            result.append({
                "id": c.id,
                "code": c.code,
                "type": c.type.value if hasattr(c.type, "value") else str(c.type),
                "value": float(c.value),
                "is_active": c.is_active,
                "usage_count": c.usage_count or 0,
                "usage_limit": c.usage_limit,
            })
    return {"coupons": result}


@router.post("/api/admin/coupons/create")
async def admin_create_coupon(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    code = (body.get("code") or "").strip().upper()
    val = float(body.get("value") or 0.0)
    c_type_str = (body.get("type") or "PERCENTAGE").upper()
    limit = int(body.get("limit") or 0) or None
    if not code or val <= 0:
        return JSONResponse({"error": "invalid_parameters"}, status_code=400)
    from enums.coupon_type import CouponType
    c_type = CouponType.PERCENTAGE if "PERCENT" in c_type_str else CouponType.FIXED
    async with get_db_session() as session:
        existing = await CouponRepository.get_by_code(code, session)
        if existing:
            return JSONResponse({"error": "coupon_already_exists"}, status_code=400)
        await CouponRepository.create(CouponDTO(
            code=code,
            type=c_type,
            value=val,
            is_active=True,
            usage_limit=limit,
            usage_count=0
        ), session)
        await session_commit(session)
    return {"status": "ok", "code": code}


@router.post("/api/admin/coupons/toggle")
async def admin_toggle_coupon(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    coupon_id = int(body.get("coupon_id") or 0)
    async with get_db_session() as session:
        stmt = select(Coupon).where(Coupon.id == coupon_id)
        coupon = (await session_execute(stmt, session)).scalar_one_or_none()
        if not coupon:
            return JSONResponse({"error": "coupon_not_found"}, status_code=404)
        coupon.is_active = not coupon.is_active
        await session_commit(session)
    return {"status": "ok", "is_active": coupon.is_active}


@router.post("/api/admin/product/update")
async def admin_update_product(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    product_id = int(body.get("product_id") or 0)
    async with get_db_session() as session:
        stmt = select(BatStoreProduct).where(BatStoreProduct.product_id == product_id)
        prod = (await session_execute(stmt, session)).scalar_one_or_none()
        if not prod:
            return JSONResponse({"error": "product_not_found"}, status_code=404)
        if "custom_name" in body:
            prod.custom_name = (body["custom_name"] or "").strip() or None
        if "category" in body:
            prod.category = (body["category"] or "").strip() or prod.category
        if "sell_price_usd" in body and body["sell_price_usd"] is not None:
            prod.sell_price_usd = float(body["sell_price_usd"])
        if "stock" in body:
            prod.stock = int(body["stock"]) if body["stock"] is not None and str(body["stock"]).strip() != "" else None
        if "hidden" in body:
            prod.hidden = bool(body["hidden"])
        await session_commit(session)
    invalidate_catalog_cache()
    return {"status": "ok", "product_id": product_id}


@router.post("/api/admin/category/update")
async def admin_update_category(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    category_id = int(body.get("category_id") or 0)
    async with get_db_session() as session:
        stmt = select(StorefrontCategory).where(StorefrontCategory.id == category_id)
        cat = (await session_execute(stmt, session)).scalar_one_or_none()
        if not cat:
            return JSONResponse({"error": "category_not_found"}, status_code=404)
        if "name_ar" in body:
            cat.name_ar = str(body["name_ar"]).strip()
        if "name_en" in body:
            cat.name_en = str(body["name_en"]).strip()
        if "image_url" in body:
            cat.image_url = str(body["image_url"]).strip()
        if "preview_ar" in body:
            cat.preview_ar = str(body["preview_ar"]).strip()
        if "preview_en" in body:
            cat.preview_en = str(body["preview_en"]).strip()
        if "sort_order" in body and body["sort_order"] is not None:
            cat.sort_order = int(body["sort_order"])
        if "hidden" in body:
            cat.hidden = bool(body["hidden"])
        await session_commit(session)
    invalidate_catalog_cache()
    return {"status": "ok", "category_id": category_id}


@router.post("/api/admin/referral/withdraw/action")
async def admin_process_referral_withdrawal(request: Request):
    """Admin approves or rejects an affiliate commission withdrawal request."""
    from bot import bot
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    withdrawal_id = int(body.get("withdrawal_id") or 0)
    action = str(body.get("action") or "").strip().lower()
    notes = str(body.get("notes") or "").strip()

    if not withdrawal_id or action not in ("approve", "reject"):
        return JSONResponse({"error": "invalid_parameters"}, status_code=400)

    async with get_db_session() as session:
        withdrawal = await ReferralWithdrawalRepository.get_by_id(withdrawal_id, session)
        if not withdrawal:
            return JSONResponse({"error": "withdrawal_not_found"}, status_code=404)
        if withdrawal.status != "pending":
            return JSONResponse({"error": "already_processed"}, status_code=400)

        user = await UserRepository.get_by_tgid(withdrawal.telegram_id, session)

        if action == "approve":
            await ReferralWithdrawalRepository.update_status(withdrawal_id, "completed", notes, session)
            await session_commit(session)
            invalidate_admin_stats_cache()
            if user:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"🎉 <b>تم تحويل أرباح الإحالة بنجاح!</b>\n\n"
                            f"• المبلغ: <b>${withdrawal.amount_usd:.2f} USD</b>\n"
                            f"• الشبكة: {withdrawal.method.upper()}\n"
                            f"• المحفظة: <code>{withdrawal.destination_address}</code>\n"
                            + (f"• ملاحظات التحويل: {notes}\n" if notes else "")
                            + "\nشكراً لجهودك كشريك مميز لـ GH Store! ✨"
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            return {"status": "ok", "action": "approved", "withdrawal_id": withdrawal_id}
        else:
            await ReferralWithdrawalRepository.update_status(withdrawal_id, "rejected", notes, session)
            await session_commit(session)
            invalidate_admin_stats_cache()
            if user:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"⚠️ <b>إشعار بشأن طلب سحب الأرباح #{withdrawal.id}:</b>\n\n"
                            f"تم رفض طلب السحب من قبل الإدارة.\n"
                            + (f"السبب: {notes}\n\n" if notes else "\n")
                            + "يرجى مراجعة بيانات المحفظة أو التواصل مع الدعم الفني للمساعدة."
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            return {"status": "ok", "action": "rejected", "withdrawal_id": withdrawal_id}


@router.post("/api/admin/orders/fulfill-supplier-recharge")
async def admin_fulfill_supplier_recharge(request: Request):
    """Admin fulfills an order queued for supplier balance recharge from the TMA admin panel."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    order_id = int(body.get("order_id") or 0)
    if not order_id:
        return JSONResponse({"error": "missing_order_id"}, status_code=400)

    async with get_db_session() as session:
        from services.supplier_recharge import SupplierRechargeService
        success, msg, goods = await SupplierRechargeService.check_and_fulfill_order(order_id, session)
        if not success:
            return JSONResponse({"error": msg}, status_code=400)
        invalidate_admin_stats_cache()
    return {"status": "ok", "message": msg, "goods": goods}
