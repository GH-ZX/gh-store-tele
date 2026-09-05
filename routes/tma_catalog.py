"""TMA Catalog, Categories, Search, and Social Proof API Routes."""
import asyncio
import datetime
import json
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select

import config
from db import get_db_session, session_commit, session_execute
from models.batstore_product import BatStoreProductDTO
from repositories.batstore_order import BatStoreOrderRepository
from repositories.batstore_product import BatStoreProductRepository
from repositories.user import UserRepository
from services.config import ConfigService
from services.notification import NotificationService
from services.telegram_auth import extract_and_verify_telegram_user
from utils.telegram import clean_tg_emojis

router = APIRouter(tags=["catalog"])

_sse_subscribers: set[asyncio.Queue] = set()
_CACHED_BOT_USERNAME: str | None = None
_USER_PHOTO_CACHE: dict = {}
_SUPPLIER_WALLETS_CACHE: dict = {"data": None, "expire_time": 0.0}
_CATALOG_CACHE: dict = {"data": None, "expire_time": 0.0}
_ADMIN_STATS_CACHE: dict = {"data": None, "expire_time": 0.0}


def invalidate_catalog_cache() -> None:
    """Flush the in-memory catalog cache so changes surface immediately."""
    _CATALOG_CACHE["data"] = None
    _CATALOG_CACHE["expire_time"] = 0.0


def invalidate_admin_stats_cache() -> None:
    """Flush the in-memory admin stats cache."""
    _ADMIN_STATS_CACHE["data"] = None
    _ADMIN_STATS_CACHE["expire_time"] = 0.0


def broadcast_sse_event(event_type: str, data: dict) -> None:
    """Emit a Server-Sent Event to all connected Mini App clients and invalidate catalog cache."""
    invalidate_catalog_cache()
    msg = json.dumps({"event": event_type, **data})
    for q in list(_sse_subscribers):
        try:
            q.put_nowait(msg)
        except Exception:
            _sse_subscribers.discard(q)


@router.get("/api/catalog")
async def get_tma_catalog():
    """API endpoint for Telegram Mini App storefront with high-performance in-memory caching."""
    now_ts = time.time()
    if _CATALOG_CACHE["data"] is not None and now_ts < _CATALOG_CACHE["expire_time"]:
        return _CATALOG_CACHE["data"]
    async with get_db_session() as session:
        from repositories.storefront_category import StorefrontCategoryRepository
        from services.product_spec import ProductSpecParser

        cats_db = await StorefrontCategoryRepository.get_all_visible(session)
        cats_list = []
        for c in cats_db:
            cats_list.append({
                "id": c.id,
                "name": c.name,
                "name_ar": c.name_ar,
                "name_en": c.name_en,
                "image_url": c.image_url,
                "icon": c.icon or "📦",
                "preview_ar": c.preview_ar,
                "preview_en": c.preview_en,
                "sort_order": c.sort_order,
            })

        if not cats_list:
            raw_cats = await BatStoreProductRepository.get_categories(session)
            cats_list = [{"id": i, "name": c, "name_ar": c, "name_en": c, "icon": "📦", "image_url": ""} for i, c in enumerate(raw_cats, 1)]

        products = await BatStoreProductRepository.get_visible(session)
        sym = config.CURRENCY.get_localized_symbol()
        data = []
        for p in products:
            specs = ProductSpecParser.parse(p.name)
            clean_title = p.custom_name or specs["clean_name"] or p.name
            data.append({
                "id": p.product_id,
                "name": p.name,
                "clean_name": clean_title,
                "category": p.category or "Other",
                "price": p.sell_price_usd,
                "cost_usd": round(float(p.cost_usd or 0.0), 2),
                "sym": sym,
                "description": clean_tg_emojis(p.description),
                "description_ar": clean_tg_emojis(getattr(p, "description_ar", None)),
                "duration_ar": specs["duration_ar"],
                "duration_en": specs["duration_en"],
                "warranty_ar": specs["warranty_ar"],
                "warranty_en": specs["warranty_en"],
                "type_ar": specs["type_ar"],
                "type_en": specs["type_en"],
                "emoji": p.emoji or "⚡",
                "custom_emoji_id": p.custom_emoji_id,
                "stock": p.stock,
                "delivery_type": p.delivery_type or "stock",
                "supplier": getattr(p, "supplier", "batstore") or "batstore",
                "server_badge": getattr(p, "server_badge", "سيرفر 1 (BatStore)") or "سيرفر 1 (BatStore)",
            })
        store_logo_url = await ConfigService.get(session, "STORE_LOGO_URL", env_fallback=os.environ.get("STORE_LOGO_URL", ""))
        flash_enabled = (await ConfigService.get(session, "FLASH_SALE_ENABLED", default="false")).lower() in ("true", "1", "yes")
        flash_pct = float(await ConfigService.get(session, "FLASH_SALE_PERCENT", default="15") or 15)
        flash_end = int(await ConfigService.get(session, "FLASH_SALE_END_TIMESTAMP", default="0") or 0)
        flash_sale = {
            "enabled": flash_enabled,
            "percent": flash_pct,
            "title_ar": await ConfigService.get(session, "FLASH_SALE_TITLE_AR", default="عروض فلاش محدودة"),
            "title_en": await ConfigService.get(session, "FLASH_SALE_TITLE_EN", default="Limited Flash Sale"),
            "end_timestamp": flash_end,
        }
        from models.promotional_banner import PromotionalBanner
        stmt_b = select(PromotionalBanner).where(PromotionalBanner.is_active == True).order_by(PromotionalBanner.sort_order.asc(), PromotionalBanner.id.desc()).limit(10)
        banners_db = (await session_execute(stmt_b, session)).scalars().all()
        banners_list = [{
            "id": b.id,
            "title_ar": b.title_ar,
            "title_en": b.title_en,
            "subtitle_ar": b.subtitle_ar,
            "subtitle_en": b.subtitle_en,
            "badge_ar": b.badge_ar,
            "badge_en": b.badge_en,
            "image_url": b.image_url,
            "target_category": b.target_category,
            "product_id": b.product_id,
        } for b in banners_db]

        result = {
            "categories": cats_list,
            "products": data,
            "store_logo_url": store_logo_url or "",
            "flash_sale": flash_sale,
            "banners": banners_list,
        }
        _CATALOG_CACHE["data"] = result
        _CATALOG_CACHE["expire_time"] = now_ts + 15.0  # 15s cache with instant event invalidation
    return result


@router.get("/api/banners")
async def get_promotional_banners():
    """Return active promotional banners sorted by sort_order."""
    async with get_db_session() as session:
        from models.promotional_banner import PromotionalBanner
        stmt = (
            select(PromotionalBanner)
            .where(PromotionalBanner.is_active == True)
            .order_by(PromotionalBanner.sort_order.asc(), PromotionalBanner.id.desc())
        )
        banners = (await session_execute(stmt, session)).scalars().all()
        return {
            "banners": [{
                "id": b.id,
                "title_ar": b.title_ar,
                "title_en": b.title_en,
                "subtitle_ar": b.subtitle_ar,
                "subtitle_en": b.subtitle_en,
                "badge_ar": b.badge_ar,
                "badge_en": b.badge_en,
                "image_url": b.image_url,
                "target_category": b.target_category,
                "product_id": b.product_id,
            } for b in banners]
        }

@router.get("/api/events")
async def sse_events(request: Request):
    """Server-Sent Events stream for real-time stock and price updates in TMA."""
    async def event_generator():
        q = asyncio.Queue()
        _sse_subscribers.add(q)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            _sse_subscribers.discard(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/api/search/demand")
async def log_search_demand(request: Request):
    """Log zero-result product searches to track customer demand."""
    from bot import redis
    try:
        body = await request.json()
        query = (body.get("query") or "").strip()
        if not query or len(query) < 2:
            return {"status": "ignored"}
        tg_id = body.get("tg_id")
        logging.info("Product demand search with 0 results: %s (tg_id: %s)", query, tg_id)
        if redis:
            await redis.zincrby("ghstore_search_demands", 1, query.lower()[:32])
        return {"status": "ok"}
    except Exception:
        return {"status": "ignored"}


@router.post("/api/search/log")
async def log_search_query(request: Request):
    """Increment search term frequency in Redis sorted set for real-time trending."""
    from bot import redis
    try:
        body = await request.json()
        q = (body.get("q") or "").strip().lower()
        if q and len(q) >= 2:
            if redis:
                await redis.zincrby("ghstore:trending_searches", 1, q[:24])
        return {"status": "ok"}
    except Exception:
        return {"status": "error"}


@router.get("/api/search/trending")
async def get_trending_searches():
    """Return trending search tags configured by admin or derived from real demand."""
    from bot import redis
    from services.config import ConfigService
    async with get_db_session() as session:
        admin_tags_raw = await ConfigService.get(session, "STORE_TRENDING_TAGS", default="")
        if admin_tags_raw and str(admin_tags_raw).strip():
            tags = [t.strip() for t in str(admin_tags_raw).split(",") if t.strip()]
            if tags:
                return {"status": "ok", "trending": tags[:8]}

    try:
        if redis:
            raw = await redis.zrevrange("ghstore:trending_searches", 0, 7)
            if raw:
                trending = [item.decode("utf-8").title() for item in raw if item]
                if trending:
                    return {"status": "ok", "trending": trending}
    except Exception:
        pass

    async with get_db_session() as session:
        from repositories.batstore_product import BatStoreProductRepository
        prods = await BatStoreProductRepository.get_all(session)
        real_names = [p.clean_name or p.name for p in prods if not getattr(p, "hidden", False) and getattr(p, "clean_name", None)]
        seen = set()
        real_tags = []
        for n in real_names:
            short = n.split()[0] if n else ""
            if short and short.lower() not in seen and len(short) > 2:
                seen.add(short.lower())
                real_tags.append(short)
            if len(real_tags) >= 6:
                break
        return {"status": "ok", "trending": real_tags}


@router.get("/api/reviews")
async def get_tma_reviews():
    """Return real customer reviews and aggregate rating score from database."""
    async with get_db_session() as session:
        from models.review import Review
        stmt = select(Review).order_by(Review.id.desc()).limit(20)
        res = await session.execute(stmt)
        reviews = list(res.scalars().all())

        total_stars = sum(r.rating for r in reviews) if reviews else 0
        avg_rating = round(total_stars / len(reviews), 1) if reviews else 0.0

        data = []
        for r in reviews:
            if not r.text:
                continue
            data.append({
                "id": r.id,
                "rating": r.rating,
                "text": r.text,
            })
        return {
            "average": avg_rating,
            "count": len(data),
            "reviews": data,
        }


@router.post("/api/reviews/submit")
async def tma_submit_review(request: Request):
    """Submit customer star rating and review directly from the Mini App."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = int(body.get("tg_id") or 0)
    try:
        tg_id = extract_and_verify_telegram_user(request, tg_id)
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    rating = int(body.get("rating") or 5)
    text = (body.get("text") or "").strip()
    order_id = body.get("order_id")

    if not tg_id or rating < 1 or rating > 5:
        return JSONResponse({"error": "invalid_rating"}, status_code=400)

    async with get_db_session() as session:
        from models.review import Review
        review = Review(
            rating=rating,
            text=text or "Instant delivery, key activated smoothly!",
            create_datetime=datetime.datetime.now(datetime.timezone.utc),
            batstore_order_id=int(order_id) if order_id else None,
        )
        session.add(review)
        await session_commit(session)
        await NotificationService.send_to_admins(
            f"⭐ <b>New Review via Mini App</b>\n\n• Rating: {'⭐' * rating} ({rating}/5)\n• From: tg:{tg_id}\n• Order: #{order_id or 'N/A'}\n• Comment: {text or 'No comment'}",
            None
        )

    return {"status": "success"}


@router.get("/api/user-data")
async def get_tma_user_data(tg_id: int, request: Request):
    from bot import bot
    try:
        tg_id = extract_and_verify_telegram_user(request, tg_id)
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)
    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            from models.user import UserDTO
            from enums.language import Language
            from services.user import UserService
            ref_code = request.query_params.get("ref") or None
            await UserService.create_if_not_exist(
                UserDTO(telegram_id=tg_id, language=Language.EN),
                ref_code,
                session
            )
            user = await UserRepository.get_by_tgid(tg_id, session)
            if not user:
                return {"error": "user_not_found"}

        from services.user import get_vip_tier_info, format_currency_display
        tier_label, discount_pct = get_vip_tier_info(user.consume_records, getattr(user, "custom_discount_pct", None))
        balance = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
        curr_pref = getattr(user, "currency_preference", "USD") or "USD"
        syp_cfg = await ConfigService.get(session, "SAM_SYP_USD_RATE", env_fallback=os.environ.get("SAM_SYP_USD_RATE"))
        syp_val = float(syp_cfg or 0.002551)
        syp_market = int(round(1.0 / syp_val)) if syp_val < 1.0 else int(round(syp_val))

        orders_db = await BatStoreOrderRepository.get_by_telegram_id(tg_id, session, limit=15)
        orders_data = []
        sym = config.CURRENCY.get_localized_symbol()
        for o in orders_db:
            goods_list = []
            product_names = []
            warranty_days = 0
            for d in (o.details or []):
                product_names.append(d.get("name") or "Product")
                warranty_days = max(warranty_days, d.get("warranty_days") or 0)
                for g in d.get("delivery_goods", []):
                    goods_list.append(str(g))

            orders_data.append({
                "id": o.id,
                "status": o.status,
                "total": o.total_sell,
                "sym": sym,
                "products": ", ".join(product_names) if product_names else "Order",
                "goods": goods_list,
                "warranty_days": warranty_days,
                "warranty_claimed": getattr(o, "warranty_claimed", False),
                "created_at": o.created_at.strftime("%b %d, %H:%M") if o.created_at else "",
                "timestamp": o.created_at.timestamp() if o.created_at else 0,
                "type": "order",
            })

        # Fetch Recharges History for Processes / Activity
        recharges_data = []
        try:
            from models.sam_payment import SamPayment
            from models.stars_payment import StarsPayment
            from models.deposit import Deposit

            from models.admin_audit_log import AdminAuditLog
            stmt_audit = select(AdminAuditLog.details).where(AdminAuditLog.action == "recharge_approved").order_by(AdminAuditLog.id.desc()).limit(50)
            audit_rows = (await session_execute(stmt_audit, session)).scalars().all()
            approved_ids = set()
            for det in audit_rows:
                if isinstance(det, dict) and det.get("recharge_id"):
                    approved_ids.add(str(det.get("recharge_id")).strip())

            # 1. SAM Payments
            stmt_sam = select(SamPayment).where(SamPayment.telegram_id == tg_id).order_by(SamPayment.id.desc()).limit(15)
            sams = (await session_execute(stmt_sam, session)).scalars().all()
            for sp in sams:
                is_admin_app = bool(f"sam_{sp.id}" in approved_ids or str(sp.invoice_id) in approved_ids or str(sp.id) in approved_ids)
                recharges_data.append({
                    "id": f"SAM-{sp.id}",
                    "invoice_id": sp.invoice_id,
                    "method": getattr(sp, "method", None) or "SAM",
                    "amount_usd": sp.usd_amount,
                    "invoice_amount": getattr(sp, "amount", 0.0),
                    "currency": sp.currency,
                    "status": "completed" if (sp.event == "invoice.paid" or is_admin_app) else "pending",
                    "payment_url": sp.payment_url,
                    "created_at": sp.created_at.strftime("%b %d, %H:%M") if sp.created_at else "",
                    "timestamp": sp.created_at.timestamp() if sp.created_at else 0,
                    "type": "recharge",
                    "approved_by_admin": is_admin_app,
                })

            # 2. Telegram Stars Payments
            stmt_stars = select(StarsPayment).where(StarsPayment.telegram_id == tg_id).order_by(StarsPayment.id.desc()).limit(15)
            stars = (await session_execute(stmt_stars, session)).scalars().all()
            for st in stars:
                recharges_data.append({
                    "id": f"STR-{st.id}",
                    "invoice_id": st.telegram_payment_charge_id,
                    "method": "Telegram Stars",
                    "amount_usd": st.usd_amount,
                    "invoice_amount": st.stars_amount,
                    "currency": "XTR",
                    "status": "completed",
                    "payment_url": "",
                    "created_at": st.created_at.strftime("%b %d, %H:%M") if st.created_at else "",
                    "timestamp": st.created_at.timestamp() if st.created_at else 0,
                    "type": "recharge",
                    "approved_by_admin": False,
                })

            # 3. Crypto Deposits
            stmt_dep = select(Deposit).where(Deposit.user_id == user.id).order_by(Deposit.id.desc()).limit(15)
            deps = (await session_execute(stmt_dep, session)).scalars().all()
            for dp_item in deps:
                recharges_data.append({
                    "id": f"CRY-{dp_item.id}",
                    "invoice_id": str(dp_item.id),
                    "method": "Crypto",
                    "amount_usd": dp_item.amount,
                    "invoice_amount": dp_item.amount,
                    "currency": "USD",
                    "status": "completed",
                    "payment_url": "",
                    "created_at": dp_item.created_at.strftime("%b %d, %H:%M") if dp_item.created_at else "",
                    "timestamp": dp_item.created_at.timestamp() if dp_item.created_at else 0,
                    "type": "recharge",
                    "approved_by_admin": False,
                })
            recharges_data.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            recharges_data = recharges_data[:15]
        except Exception as e:
            logging.error("Failed to compile user recharges: %s", e)

        if not user.referral_code:
            import secrets
            import string
            user.referral_code = f"U_{''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))}"
            await UserRepository.update(user, session)
            await session_commit(session)

        referrals_count = await UserRepository.get_referrals_qty_by_referrer_id(user.id, session)
        from repositories.referral import ReferralRepository
        referrals_total_earned = await ReferralRepository.get_bonus_sum_as_referrer(user.id, session)
        referrals_breakdown = await ReferralRepository.get_referrals_breakdown(user.id, session)
        global _CACHED_BOT_USERNAME
        if _CACHED_BOT_USERNAME is None:
            try:
                me_obj = await bot.get_me()
                _CACHED_BOT_USERNAME = me_obj.username or ""
            except Exception:
                _CACHED_BOT_USERNAME = ""
        bot_username = _CACHED_BOT_USERNAME

        now_ts = time.time()
        photo_entry = _USER_PHOTO_CACHE.get(user.telegram_id)
        if photo_entry and photo_entry[1] > now_ts:
            photo_url = photo_entry[0]
        else:
            photo_url = None
            try:
                photos = await bot.get_user_profile_photos(user.telegram_id, limit=1)
                if photos.total_count > 0:
                    file_id = photos.photos[0][-1].file_id
                    file_obj = await bot.get_file(file_id)
                    photo_url = f"https://api.telegram.org/file/bot{config.TOKEN}/{file_obj.file_path}"
            except Exception as e:
                logging.debug("Could not fetch profile photo: %s", e)
            _USER_PHOTO_CACHE[user.telegram_id] = (photo_url, now_ts + 3600.0)

        is_admin = bool(
            user.telegram_id in config.ADMIN_ID_LIST
            or (user.telegram_username and user.telegram_username.lower() == "ahmedghx")
        )
        admin_stats = None
        if is_admin:
            now_w = time.time()
            force_refresh = request.query_params.get("refresh_wallets") == "true"
            if not force_refresh and _ADMIN_STATS_CACHE["data"] is not None and now_w < _ADMIN_STATS_CACHE["expire_time"]:
                admin_stats = _ADMIN_STATS_CACHE["data"]
            else:
                try:
                    from decimal import Decimal as _ProfitDecimal
                    from models.batstore_order import BatStoreOrder
                    from models.user import User
                    from services.sale_pricing import order_cost as _order_cost

                    stmt_rev = select(func.coalesce(func.sum(BatStoreOrder.total_sell), 0.0)).where(BatStoreOrder.status == "completed")
                    tot_rev = (await session_execute(stmt_rev, session)).scalar_one()
                    stmt_cost_orders = select(BatStoreOrder.details).where(BatStoreOrder.status == "completed")
                    cost_rows = (await session_execute(stmt_cost_orders, session)).scalars().all()
                    tot_cost = round(float(sum((_order_cost(d) for d in cost_rows), _ProfitDecimal(0))), 2)
                    tot_profit = round(float(tot_rev or 0.0) - tot_cost, 2)
                    stmt_ord = select(func.count(BatStoreOrder.id))
                    tot_ord = (await session_execute(stmt_ord, session)).scalar_one()
                    stmt_usr = select(func.count(User.id))
                    tot_usr = (await session_execute(stmt_usr, session)).scalar_one()
                    stmt_bal = select(func.coalesce(func.sum(func.coalesce(User.top_up_amount, 0.0) - func.coalesce(User.consume_records, 0.0)), 0.0))
                    tot_bal = (await session_execute(stmt_bal, session)).scalar_one()

                    syp_cfg = await ConfigService.get(session, "SAM_SYP_USD_RATE", env_fallback=os.environ.get("SAM_SYP_USD_RATE"))
                    syp_val = float(syp_cfg or 0.002551)
                    syp_market = int(round(1.0 / syp_val)) if syp_val < 1.0 else int(round(syp_val))
                    ref_cfg = await ConfigService.get(session, "REFERRAL_MARGIN_COMMISSION_PERCENT", default="0.2")
                    ref_val = float(ref_cfg or 0.2)
                    margin_cfg = await ConfigService.get(session, "MARGIN_PERCENT", default="20")
                    stars_cfg = await ConfigService.get(session, "GHSTORE_STARS_TO_USD", default="0.01")
                    announcement_cfg = await ConfigService.get(session, "STORE_ANNOUNCEMENT", default="")

                    if force_refresh or _SUPPLIER_WALLETS_CACHE["data"] is None or now_w >= _SUPPLIER_WALLETS_CACHE["expire_time"]:
                        from services.batstore import BatStoreService
                        from services.prodseller import ProdSellerService
                        bat_bal = await BatStoreService.get_cached_reseller_balance(session)
                        prod_bal = await ProdSellerService.get_cached_balance(session)
                        total_supp = round(bat_bal + prod_bal, 2)
                        _SUPPLIER_WALLETS_CACHE["data"] = {
                            "batstore_usd": bat_bal,
                            "prodseller_usd": prod_bal,
                            "total_supplier_usd": total_supp,
                        }
                        _SUPPLIER_WALLETS_CACHE["expire_time"] = now_w + 300.0
                    supp_wallets = _SUPPLIER_WALLETS_CACHE["data"]

                    autorefund_mode = await ConfigService.get(session, "AUTOREFUND_FAILED_ORDERS", default="true")
                    is_autorefund = str(autorefund_mode).lower() in ("true", "1", "yes")

                    admin_stats = {
                        "total_revenue": round(float(tot_rev or 0.0), 2),
                        "total_cost": tot_cost,
                        "total_profit": tot_profit,
                        "total_orders": int(tot_ord or 0),
                        "total_users": int(tot_usr or 0),
                        "total_user_balances": round(float(tot_bal or 0.0), 2),
                        "syp_usd_rate": syp_market,
                        "referral_commission_percent": ref_val,
                        "global_margin_percent": float(margin_cfg or 20.0),
                        "stars_to_usd_rate": float(stars_cfg or 0.01),
                        "store_announcement": announcement_cfg or "",
                        "store_logo_url": await ConfigService.get(session, "STORE_LOGO_URL", env_fallback=os.environ.get("STORE_LOGO_URL", "")),
                        "autorefund_enabled": is_autorefund,
                        "supplier_wallets": supp_wallets,
                    }
                    _ADMIN_STATS_CACHE["data"] = admin_stats
                    _ADMIN_STATS_CACHE["expire_time"] = now_w + 60.0
                except Exception as e:
                    logging.error("Failed to compile admin stats: %s", e)
        return {
            "telegram_id": user.telegram_id,
            "username": user.telegram_username or "",
            "language": getattr(user.language, "value", user.language) if getattr(user, "language", None) else "ar",
            "photo_url": photo_url,
            "balance": balance,
            "currency_preference": curr_pref,
            "formatted_balance": format_currency_display(balance, curr_pref, syp_market),
            "vip_tier": tier_label,
            "vip_discount": discount_pct,
            "total_spent": round(user.consume_records or 0.0, 2),
            "referral_code": user.referral_code or "",
            "bot_username": bot_username or "GHStoreBot",
            "referrals_count": referrals_count,
            "referrals_total_earned": round(float(referrals_total_earned or 0.0), 2),
            "referrals_breakdown": referrals_breakdown,
            "referral_commission_rate": 0.2,
            "is_admin": is_admin,
            "admin_stats": admin_stats,
            "orders": orders_data,
            "recharges": recharges_data,
            "store_announcement": await ConfigService.get(session, "STORE_ANNOUNCEMENT", env_fallback=""),
            "store_trending_tags": await ConfigService.get(session, "STORE_TRENDING_TAGS", env_fallback=""),
        }


@router.post("/api/user/settings")
async def update_tma_user_settings(request: Request):
    """Update user language or currency preference directly from the Mini App."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = body.get("tg_id")
    if not tg_id:
        return JSONResponse({"error": "missing_tg_id"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(tg_id))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(int(tg_id), session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        if "currency" in body:
            user.currency_preference = str(body["currency"]).upper()
        if "language" in body:
            from enums.language import Language
            try:
                user.language = Language(body["language"].lower())
            except Exception:
                pass

        await UserRepository.update(user, session)
        await session_commit(session)

    return {"status": "ok"}


@router.post("/api/user/channel-perk")
async def claim_channel_perk(request: Request):
    """Verify channel membership and reward customer with an exclusive channel perk."""
    from bot import bot
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = body.get("tg_id")
    if not tg_id:
        return JSONResponse({"error": "missing_tg_id"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(tg_id))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    from services.user import UserService
    is_member = await UserService.check_channel_membership(bot, tg_id)
    if not is_member:
        return JSONResponse({"status": "not_member", "message": "Please join the official channel to unlock your perk."}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        # Grant 5% custom VIP perk if customer doesn't already have a higher discount
        curr_disc = getattr(user, "custom_discount_pct", 0.0) or 0.0
        if curr_disc < 5.0:
            user.custom_discount_pct = 5.0
            await UserRepository.update(user, session)
            await session_commit(session)
            return {"status": "success", "message": "Channel member verified! 5% VIP discount applied to your account.", "discount_pct": 5.0}

    return {"status": "already_active", "message": "You already enjoy channel VIP benefits!", "discount_pct": curr_disc}


@router.post("/api/share/prepare")
async def prepare_share_message(request: Request):
    """Bot API 8.0: Prepare an inline message for native 1-tap sharing via tg.shareMessage."""
    from bot import bot
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    product_id = int(body.get("product_id") or 0)
    tg_id = int(body.get("tg_id") or 0)
    if not product_id or not tg_id:
        return JSONResponse({"error": "missing_params"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, tg_id)
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    async with get_db_session() as session:
        prod = await BatStoreProductRepository.get_by_product_id(product_id, session)
        if not prod:
            return JSONResponse({"error": "product_not_found"}, status_code=404)

        bot_obj = await bot.get_me()
        bot_user = bot_obj.username or "GHStoreBot"
        tma_link = f"https://t.me/{bot_user}/app?startapp=prod_{prod.product_id}_ref_{tg_id}"

        from aiogram.types import (
            InlineQueryResultArticle,
            InputTextMessageContent,
            InlineKeyboardMarkup,
            InlineKeyboardButton,
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ عرض المنتج في المتجر (1-Tap)", url=tma_link)]
        ])
        msg_content = InputTextMessageContent(
            message_text=(
                f"🛍️ <b>{prod.name}</b>\n\n"
                f"💰 <b>السعر:</b> ${prod.sell_price_usd:.2f}\n"
                f"⚡ <b>التسليم:</b> تسليم تلقائي فوري مع ضمان كامل!\n\n"
                f"تسوق الآن عبر متجر GH Store الرقمي:"
            ),
            parse_mode="HTML"
        )
        res_article = InlineQueryResultArticle(
            id=f"share_{prod.product_id}",
            title=f"{prod.name} - ${prod.sell_price_usd:.2f}",
            description="انقر لإرسال بطاقة المنتج ومشاركتها في المحادثة",
            input_message_content=msg_content,
            reply_markup=kb,
        )
        try:
            prep = await bot.save_prepared_inline_message(
                user_id=tg_id,
                result=res_article,
                allow_user_chats=True,
                allow_bot_chats=True,
                allow_group_chats=True,
                allow_channel_chats=True,
            )
            return {"status": "ok", "prepared_message_id": prep.id}
        except Exception as e:
            logging.error("Failed to save prepared inline message: %s", e)
            return JSONResponse({"error": "failed_to_prepare", "detail": str(e)}, status_code=500)
