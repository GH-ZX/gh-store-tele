import asyncio
import datetime
import os
import logging
import sys
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BufferedInputFile, URLInputFile
from redis.asyncio import Redis
from sqladmin import Admin

import config
from utils.telegram import clean_tg_emojis
from aiogram import Dispatcher
from fastapi import FastAPI, Request, status, HTTPException
from sqlalchemy import select, func, text

from admin import authentication_backend
from db import create_db_and_tables, engine, get_db_session, session_commit, session_execute
from processing.processing import processing_router
import uvicorn
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from enums.cryptocurrency import Cryptocurrency
from models.buy import BuyAdmin
from models.buyItem import BuyItemAdmin
from models.cart import CartAdmin
from models.cartItem import CartItemAdmin
from models.category import CategoryAdmin
from models.coupon import CouponAdmin
from models.deposit import DepositAdmin
from models.item import ItemAdmin
from models.payment import PaymentAdmin
from models.referral import ReferralBonusAdmin
from models.review import ReviewAdmin
from models.shipping_option import ShippingOptionAdmin
from models.subcategory import SubcategoryAdmin
from models.user import UserAdmin
from models.app_config import AppConfigAdmin
from models.batstore_product import BatStoreProductAdmin
from models.batstore_order import BatStoreOrderAdmin
from models.sam_payment import SamPaymentAdmin, SamPaymentDTO
from models.restock_subscription import RestockSubscriptionAdmin
from models.stars_payment import StarsPaymentAdmin
from models.admin_audit_log import AdminAuditLogAdmin
from models.gift_voucher import GiftVoucherAdmin
from models.storefront_category import StorefrontCategoryAdmin
from repositories.gift_voucher import GiftVoucherRepository
from services.cart_recovery import CartRecoveryService, cart_recovery_cron
from repositories.sam_payment import SamPaymentRepository
from repositories.user import UserRepository
from repositories.button_media import ButtonMediaRepository
from repositories.batstore_product import BatStoreProductRepository
from repositories.batstore_order import BatStoreOrderRepository
from services.config import ConfigService
from services.batstore import BatStoreService
from services.referral import ReferralService
from services.sam import SamService, SamAPIError
from services.media import MediaService
from services.notification import NotificationService
from services.wallet import WalletService
from utils.telegram import create_bot, create_telegram_session
from utils.utils import validate_i18n

redis = Redis(host=config.REDIS_HOST, password=config.REDIS_PASSWORD)
session = create_telegram_session()
bot = create_bot(config.TOKEN, session)
NotificationService.set_bot(bot)
BatStoreProductRepository.set_redis(redis)
authentication_backend.set_redis(redis)
dp = Dispatcher(storage=RedisStorage(redis))
CartRecoveryService.set_redis(redis)


async def _set_webhook_with_retry() -> None:
    """Register the Telegram webhook, retrying until the hostname resolves.

    The webhook host (e.g. bot.gh-store.me behind a Cloudflare Tunnel) may not be
    reachable/in-DNS yet when the bot first boots. Rather than crash-loop, retry
    with a short backoff so startup completes automatically once the tunnel/cname is
    live.
    """
    import asyncio as _asyncio
    import time as _time

    while True:
        try:
            await bot.set_webhook(
                url=config.WEBHOOK_URL,
                secret_token=config.WEBHOOK_SECRET_TOKEN
            )
            return
        except Exception as e:  # noqa: BLE001 - webhook may fail while DNS settles
            logging.error(
                "Webhook registration failed for %s (%s). Retrying in 15s...",
                config.WEBHOOK_URL, e,
            )
            await _asyncio.sleep(15)


async def _sync_all_supplier_catalogs() -> None:
    """Sync catalogs from all suppliers (BatStore and ProdSeller) on startup."""
    try:
        async with get_db_session() as session:
            from services.multi_supplier import MultiSupplierService
            res = await MultiSupplierService.sync_all_suppliers(session)
        logging.info("All supplier catalogs synced: %s", res)
    except Exception as e:  # noqa: BLE001
        logging.error("Supplier catalog sync failed (continuing): %s", e)

_polling_task: asyncio.Task | None = None
_sync_loop_task: asyncio.Task | None = None
_balance_monitor_task: asyncio.Task | None = None
_digest_task: asyncio.Task | None = None
_recovery_task: asyncio.Task | None = None
_rates_task: asyncio.Task | None = None
_backup_task: asyncio.Task | None = None
async def _startup() -> None:
    global _polling_task
    await create_db_and_tables()
    async with get_db_session() as session:
        await ConfigService.seed_defaults(session)
        await ConfigService.seed_from_env(session)
    if config.BATSTORE_SYNC_ENABLED or getattr(config, "PRODSELLER_SYNC_ENABLED", True):
        asyncio.create_task(_sync_all_supplier_catalogs())
    asyncio.create_task(_set_webhook_with_retry())
    try:
        tma_host = (config.WEBHOOK_HOST or "").strip().rstrip('/')
        if tma_host and tma_host.startswith("https://"):
            from aiogram.types import MenuButtonWebApp, WebAppInfo
            tma_url = f"{tma_host}/app"
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🛍️ Store",
                    web_app=WebAppInfo(url=tma_url)
                )
            )
            logging.info("Telegram Mini App menu button configured: %s", tma_url)
    except Exception as e:
        logging.warning("Could not set chat menu button: %s", e)
    try:
        from aiogram.types import BotCommand
        commands = [
            BotCommand(command="start", description="🛍️ Open Store & Main Menu"),
            BotCommand(command="search", description="🔍 Find Digital Accounts & Keys"),
            BotCommand(command="redeem", description="🎟️ Redeem Gift Voucher Code"),
            BotCommand(command="help", description="💬 Support & Help"),
        ]
        await bot.set_my_commands(commands)
        logging.info("Telegram Bot command menu set successfully")
    except Exception as e:
        logging.warning("Could not set bot commands: %s", e)
    from services.order_polling import poll_pending_orders, periodic_catalog_sync, periodic_balance_monitor
    _polling_task = asyncio.create_task(poll_pending_orders())
    _sync_loop_task = asyncio.create_task(periodic_catalog_sync())
    _balance_monitor_task = asyncio.create_task(periodic_balance_monitor())
    from services.financial_digest import daily_digest_cron
    _digest_task = asyncio.create_task(daily_digest_cron())
    _recovery_task = asyncio.create_task(cart_recovery_cron())
    from services.backup_service import periodic_backup_cron
    _backup_task = asyncio.create_task(periodic_backup_cron())
    from services.currency_rates import currency_rates_cron, CurrencyRateService
    _rates_task = asyncio.create_task(currency_rates_cron())
    asyncio.create_task(CurrencyRateService.update_rates())
    static = Path("static")
    if static.exists() is False:
        static.mkdir()
    me = await bot.get_me()
    photos = await bot.get_user_profile_photos(me.id)
    if photos.total_count == 0:
        photo_id_list = []
        for admin_id in config.ADMIN_ID_LIST:
            try:
                msg = await bot.send_photo(chat_id=admin_id,
                                           photo=URLInputFile(url="https://img.freepik.com/premium-vector/no-photo-available-vector-icon-default-image-symbol-picture-coming-soon-web-site-mobile-app_87543-18055.jpg",
                                                              filename="no_image.png"))
                bot_photo_id = msg.photo[-1].file_id
                photo_id_list.append(bot_photo_id)
            except Exception as e:
                logging.warning("Could not send fallback photo to admin %s: %s", admin_id, e)
        bot_photo_id = photo_id_list[0] if photo_id_list else None
    else:
        bot_photo_id = photos.photos[0][-1].file_id
    if bot_photo_id is None:
        logging.warning("No bot/fallback profile photo obtained; skipping media init.")
    else:
        try:
            with open("static/no_image.jpeg", "w") as f:
                f.write(bot_photo_id)
            await MediaService.update_inaccessible_media(bot)
        except Exception as e:
            logging.warning("update_inaccessible_media skipped: %s", e)
    validate_i18n()
    await ButtonMediaRepository.init_buttons_media()
    if config.CRYPTO_FORWARDING_MODE:
        for cryptocurrency in Cryptocurrency:
            forwarding_address = cryptocurrency.get_forwarding_address()
            is_addr_valid = WalletService.validate_withdrawal_address(forwarding_address, cryptocurrency)
            if is_addr_valid is False:
                logging.error(
                    "Your withdrawal address for %s cryptocurrency is not configured correctly: %s",
                    cryptocurrency.name,
                    forwarding_address
                )
                sys.exit(1)
    for admin in config.ADMIN_ID_LIST:
        try:
            await bot.send_message(admin, 'Bot is working')
        except Exception as e:
            logging.warning(e)


async def _shutdown() -> None:
    global _polling_task, _sync_loop_task, _balance_monitor_task, _digest_task, _recovery_task, _rates_task
    logging.warning('Shutting down..')
    for t in (_polling_task, _sync_loop_task, _balance_monitor_task, _digest_task, _recovery_task, _rates_task):
        if t and not t.done():
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
    await bot.delete_webhook()
    await dp.storage.close()
    await bot.session.close()
    await BatStoreService.close_client()
    await SamService.close_client()
    logging.warning('Bye!')


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _startup()
    try:
        yield
    finally:
        await _shutdown()


app = FastAPI(lifespan=lifespan)
from middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware, redis_client=redis)


@app.middleware("http")
async def _no_cache_admin(request: Request, call_next):
    """Never cache admin pages so settings changes always show immediately."""
    response = await call_next(request)
    if request.url.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


admin = Admin(app=app, engine=engine, authentication_backend=authentication_backend,
              title="GH Store Admin")
admin.add_model_view(UserAdmin)
admin.add_model_view(BuyAdmin)
admin.add_model_view(ShippingOptionAdmin)
admin.add_model_view(CouponAdmin)
admin.add_model_view(CategoryAdmin)
admin.add_model_view(SubcategoryAdmin)
admin.add_model_view(ItemAdmin)
admin.add_model_view(DepositAdmin)
admin.add_model_view(BuyItemAdmin)
admin.add_model_view(PaymentAdmin)
admin.add_model_view(CartAdmin)
admin.add_model_view(CartItemAdmin)
admin.add_model_view(ReferralBonusAdmin)
admin.add_model_view(ReviewAdmin)
admin.add_model_view(AppConfigAdmin)
admin.add_model_view(BatStoreProductAdmin)
admin.add_model_view(BatStoreOrderAdmin)
admin.add_model_view(SamPaymentAdmin)
admin.add_model_view(RestockSubscriptionAdmin)
admin.add_model_view(StarsPaymentAdmin)
admin.add_model_view(StorefrontCategoryAdmin)
from models.referral_withdrawal import ReferralWithdrawalAdmin
admin.add_model_view(ReferralWithdrawalAdmin)
app.include_router(processing_router)
from fastapi.staticfiles import StaticFiles
_static_dir = Path(__file__).resolve().parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
@app.get("/health")
@app.get("/status")
async def health_check():
    """Health check endpoint for Docker, Cloudflare, and external uptime monitors."""
    from sqlalchemy import text
    db_ok = False
    redis_ok = False
    try:
        async with get_db_session() as session:
            res = await session.execute(text("SELECT 1"))
            db_ok = res.scalar() == 1
    except Exception as e:
        logging.warning("Health check DB check failed: %s", e)

    try:
        redis_ok = bool(await redis.ping())
    except Exception as e:
        logging.warning("Health check Redis ping failed: %s", e)

    status_code = 200 if (db_ok and redis_ok) else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if (db_ok and redis_ok) else "degraded",
            "postgres": "connected" if db_ok else "disconnected",
            "redis": "connected" if redis_ok else "disconnected",
            "stars_enabled": bool(config.GHSTORE_STARS_ENABLED),
            "batstore_sync": bool(config.BATSTORE_SYNC_ENABLED),
        },
    )



@app.get("/api/catalog")
async def get_tma_catalog():
    """API endpoint for Telegram Mini App storefront."""
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
            "end_timestamp": flash_end,
            "title_ar": await ConfigService.get(session, "FLASH_SALE_TITLE_AR", default="عروض فلاش محدودة 🔥"),
            "title_en": await ConfigService.get(session, "FLASH_SALE_TITLE_EN", default="Limited Flash Sale 🔥"),
        }
    return {"categories": cats_list, "products": data, "store_logo_url": store_logo_url or "", "flash_sale": flash_sale}


_sse_subscribers: set[asyncio.Queue] = set()

def broadcast_sse_event(event_type: str, data: dict) -> None:
    """Emit a Server-Sent Event to all connected Mini App clients."""
    import json
    msg = json.dumps({"event": event_type, **data})
    for q in list(_sse_subscribers):
        try:
            q.put_nowait(msg)
        except Exception:
            pass


@app.get("/api/events")
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


@app.post("/api/search/demand")
async def log_search_demand(request: Request):
    """Log zero-result product searches to track customer demand."""
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


@app.get("/api/reviews")
async def get_tma_reviews():
    """Return customer reviews and aggregate rating score for social proof in TMA."""
    async with get_db_session() as session:
        from models.review import Review
        stmt = select(Review).order_by(Review.id.desc()).limit(20)
        res = await session.execute(stmt)
        reviews = list(res.scalars().all())

        total_stars = sum(r.rating for r in reviews) if reviews else 0
        avg_rating = round(total_stars / len(reviews), 1) if reviews else 4.9

        data = []
        for r in reviews:
            data.append({
                "id": r.id,
                "rating": r.rating,
                "text": r.text or "Instant automated delivery, key activated smoothly!",
            })
        return {
            "average": avg_rating,
            "count": max(len(reviews), 28),
            "reviews": data,
        }

_CACHED_BOT_USERNAME: str | None = None
_USER_PHOTO_CACHE: dict = {}
_SUPPLIER_WALLETS_CACHE: dict = {"data": None, "expire_time": 0.0}

@app.get("/api/user-data")
async def get_tma_user_data(tg_id: int, request: Request):
    from services.telegram_auth import extract_and_verify_telegram_user
    try:
        tg_id = extract_and_verify_telegram_user(request, tg_id)
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)
    async with get_db_session() as session:
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

            # 1. SAM Payments (ShamCash & SyriatelCash)
            stmt_sam = select(SamPayment).where(SamPayment.telegram_id == user.telegram_id).order_by(SamPayment.id.desc()).limit(20)
            sam_rows = (await session_execute(stmt_sam, session)).scalars().all()
            for sp in sam_rows:
                st = "completed" if sp.event == "invoice.paid" else ("failed" if sp.event == "invoice.expired" else "pending")
                recharges_data.append({
                    "id": f"sam_{sp.id}",
                    "raw_id": sp.id,
                    "type": "recharge",
                    "method": sp.method or "shamcash",
                    "status": st,
                    "amount_usd": float(sp.usd_amount or 0.0),
                    "invoice_amount": float(sp.amount or 0.0),
                    "currency": sp.currency or "USD",
                    "invoice_id": sp.invoice_id or "",
                    "payment_url": sp.payment_url or "",
                    "created_at": sp.created_at.strftime("%b %d, %H:%M") if getattr(sp, "created_at", None) else "",
                    "timestamp": sp.created_at.timestamp() if getattr(sp, "created_at", None) else 0,
                })

            # 2. Stars Payments
            stmt_stars = select(StarsPayment).where(StarsPayment.telegram_id == user.telegram_id).order_by(StarsPayment.id.desc()).limit(20)
            stars_rows = (await session_execute(stmt_stars, session)).scalars().all()
            for stp in stars_rows:
                recharges_data.append({
                    "id": f"stars_{stp.id}",
                    "raw_id": stp.id,
                    "type": "recharge",
                    "method": "stars",
                    "status": "completed",
                    "amount_usd": float(stp.usd_amount or 0.0),
                    "invoice_amount": float(stp.stars_amount or 0.0),
                    "currency": "XTR",
                    "invoice_id": stp.telegram_payment_charge_id or "",
                    "payment_url": "",
                    "created_at": stp.created_at.strftime("%b %d, %H:%M") if getattr(stp, "created_at", None) else "",
                    "timestamp": stp.created_at.timestamp() if getattr(stp, "created_at", None) else 0,
                })

            # 3. Crypto Deposits
            stmt_dep = select(Deposit).where(Deposit.user_id == user.id).order_by(Deposit.id.desc()).limit(20)
            dep_rows = (await session_execute(stmt_dep, session)).scalars().all()
            for dp in dep_rows:
                recharges_data.append({
                    "id": f"dep_{dp.id}",
                    "raw_id": dp.id,
                    "type": "recharge",
                    "method": "crypto",
                    "status": "completed",
                    "amount_usd": float(dp.fiat_amount or 0.0),
                    "invoice_amount": float(dp.fiat_amount or 0.0),
                    "currency": "USD",
                    "invoice_id": f"DEP-{dp.id}",
                    "payment_url": "",
                    "created_at": dp.deposit_datetime.strftime("%b %d, %H:%M") if getattr(dp, "deposit_datetime", None) else "",
                    "timestamp": dp.deposit_datetime.timestamp() if getattr(dp, "deposit_datetime", None) else 0,
                })

            recharges_data.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        except Exception as e:
            logging.error("Failed to compile user recharges: %s", e)

        if not user.referral_code:
            import string, secrets
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

        # High-speed cached Telegram profile photo (1 hour TTL)
        import time
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

        is_admin = bool(user.telegram_id in config.ADMIN_ID_LIST)
        admin_stats = None
        if is_admin:
            try:
                from models.batstore_order import BatStoreOrder
                from models.user import User
                stmt_rev = select(func.coalesce(func.sum(BatStoreOrder.total_sell), 0.0)).where(BatStoreOrder.status == "completed")
                tot_rev = (await session_execute(stmt_rev, session)).scalar_one()
                stmt_cost_orders = select(BatStoreOrder.details).where(BatStoreOrder.status == "completed")
                cost_rows = (await session_execute(stmt_cost_orders, session)).scalars().all()
                from decimal import Decimal as _ProfitDecimal
                from services.sale_pricing import order_cost as _order_cost
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

                ref_cfg = await ConfigService.get(session, "REFERRAL_MARGIN_COMMISSION_PERCENT", env_fallback="0.2")
                ref_val = float(ref_cfg or 0.2)
                margin_cfg = await ConfigService.get(session, "GLOBAL_MARGIN_PERCENT", env_fallback=os.environ.get("GLOBAL_MARGIN_PERCENT", "20"))
                stars_cfg = await ConfigService.get(session, "GHSTORE_STARS_TO_USD", env_fallback=os.environ.get("GHSTORE_STARS_TO_USD", "0.01"))
                announcement_cfg = await ConfigService.get(session, "STORE_ANNOUNCEMENT", env_fallback="")

                # Fetch supplier wallet balances with concurrent TTL cache (60s)
                global _SUPPLIER_WALLETS_CACHE
                force_refresh = (request.query_params.get("refresh_wallets") == "true")
                if not force_refresh and _SUPPLIER_WALLETS_CACHE["data"] and _SUPPLIER_WALLETS_CACHE["expire_time"] > now_ts:
                    supplier_wallets = _SUPPLIER_WALLETS_CACHE["data"]
                else:
                    async def _get_batstore():
                        try:
                            from services.batstore import BatStoreService
                            me_info = await asyncio.wait_for(BatStoreService.me(session), timeout=2.5)
                            raw_b = me_info.get("wallet_balance")
                            if raw_b is None:
                                raw_b = me_info.get("wallet", {}).get("balance", 0.0)
                            return round(float(raw_b or 0.0), 2)
                        except Exception as e:
                            logging.warning("Could not fetch BatStore balance: %s", e)
                            prev = _SUPPLIER_WALLETS_CACHE.get("data") or {}
                            return prev.get("batstore_usd", 0.08)
                    async def _get_prodseller():
                        try:
                            from services.prodseller import ProdSellerService
                            info = await asyncio.wait_for(ProdSellerService.get_balance(session), timeout=2.5)
                            return round(float(info.get("balance") or 0.0), 2)
                        except Exception as e:
                            logging.warning("Could not fetch ProdSeller balance: %s", e)
                            prev = _SUPPLIER_WALLETS_CACHE.get("data") or {}
                            return prev.get("prodseller_usd", 13.18)

                    async def _get_sam():
                        sam_acc = {"usd": 0.0, "syp": 0.0}
                        try:
                            from services.sam import SamService
                            wallets = await asyncio.wait_for(SamService.list_wallets(session), timeout=2.5)
                            base, key = await SamService._resolve(session)
                            async with await SamService._client() as client:
                                for w in wallets:
                                    prov = w.get("provider") or "shamcash"
                                    addr = w.get("walletAddress") or w.get("id") or w.get("phone")
                                    if addr:
                                        try:
                                            b_resp = await asyncio.wait_for(
                                                client.get(f"{base}/v1/wallets/{prov}/{addr}/balance", headers=SamService._headers(key)),
                                                timeout=1.5
                                            )
                                            if b_resp.status_code == 200:
                                                b_data = b_resp.json()
                                                if isinstance(b_data, list):
                                                    for b_item in b_data:
                                                        curr = (b_item.get("currency") or "").upper()
                                                        amt = float(b_item.get("amount") or 0.0)
                                                        if curr == "USD":
                                                            sam_acc["usd"] = round(sam_acc["usd"] + amt, 2)
                                                        elif curr == "SYP":
                                                            sam_acc["syp"] = round(sam_acc["syp"] + amt, 2)
                                        except Exception:
                                            pass
                        except Exception as e:
                            logging.warning("Could not fetch SAM balance: %s", e)
                            prev = _SUPPLIER_WALLETS_CACHE.get("data") or {}
                            sam_acc["usd"] = prev.get("sam_usd", 0.0)
                            sam_acc["syp"] = prev.get("sam_syp", 0.0)
                        return sam_acc

                    try:
                        bat_val, prod_val, sam_val = await asyncio.gather(_get_batstore(), _get_prodseller(), _get_sam())
                        supplier_wallets = {
                            "batstore_usd": bat_val,
                            "prodseller_usd": prod_val,
                            "sam_usd": sam_val["usd"],
                            "sam_syp": sam_val["syp"],
                            "total_supplier_usd": round(bat_val + prod_val + sam_val["usd"], 2),
                        }
                        _SUPPLIER_WALLETS_CACHE = {"data": supplier_wallets, "expire_time": now_ts + 60.0}
                    except Exception as e:
                        supplier_wallets = _SUPPLIER_WALLETS_CACHE.get("data") or {"batstore_usd": 0.08, "prodseller_usd": 13.18, "sam_usd": 0.0, "sam_syp": 0.0, "total_supplier_usd": 13.26}
                admin_stats = {
                    "total_revenue": round(float(tot_rev), 2),
                    "total_cost": tot_cost,
                    "gross_profit": tot_profit,
                    "total_orders_count": int(tot_ord),
                    "total_users_count": int(tot_usr),
                    "total_users_balance": round(float(tot_bal), 2),
                    "syp_usd_rate": syp_market,
                    "referral_commission_percent": ref_val,
                    "global_margin_percent": float(margin_cfg or 20.0),
                    "stars_to_usd_rate": float(stars_cfg or 0.01),
                    "store_announcement": announcement_cfg or "",
                    "autorefund_enabled": (await ConfigService.get(session, "AUTOREFUND_ENABLED", default="false")).lower() in ("true", "1", "yes"),
                    "supplier_wallets": supplier_wallets,
                    "supplier_routing_strategy": await ConfigService.get(session, "SUPPLIER_ROUTING_STRATEGY", default="auto_cheapest"),
                    "prodseller_api_key_set": bool(await ConfigService.get(session, "PRODSELLER_API_KEY")),
                }
            except Exception as e:
                logging.error("Failed to compile admin stats: %s", e)
        return {
            "telegram_id": user.telegram_id,
            "username": user.telegram_username or "",
            "photo_url": photo_url,
            "balance": balance,
            "display_balance": format_currency_display(balance, curr_pref, syp_rate=syp_market),
            "currency_preference": curr_pref,
            "syp_rate": syp_market,
            "language": user.language.value if hasattr(user.language, "value") else str(user.language),
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
            "store_logo_url": await ConfigService.get(session, "STORE_LOGO_URL", env_fallback=os.environ.get("STORE_LOGO_URL", "")),
            "store_announcement": await ConfigService.get(session, "STORE_ANNOUNCEMENT", env_fallback=""),
        }


@app.post("/api/user/settings")
async def update_tma_user_settings(request: Request):
    """Update user language or currency preference directly from the Mini App."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = body.get("tg_id")
    if not tg_id:
        return JSONResponse({"error": "missing_tg_id"}, status_code=400)

    from services.telegram_auth import extract_and_verify_telegram_user
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


@app.post("/api/buy")
async def tma_instant_buy(request: Request):
    """In-app checkout for Telegram Mini App. Customers stay in the app without text chat redirect."""
    import uuid
    from models.batstore_order import BatStoreOrderDTO
    from services.user import get_vip_tier_info

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    from services.telegram_auth import extract_and_verify_telegram_user
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

            # Multi-Supplier Balance Circuit Breaker
            from services.multi_supplier import MultiSupplierService
            from services.batstore import BatStoreOutOfStockError
            from services.prodseller import ProdSellerOutOfStockError
            total_cost = (product.cost_usd or 0.0) * quantity
            supplier_bal = await MultiSupplierService.get_cached_supplier_balance(product, session, redis)
            if supplier_bal < total_cost:
                return JSONResponse({
                    "error": "supplier_replenishing",
                    "message": "المتجر يقوم حالياً بإعادة شحن الرصيد لدى المورد. يرجى إعادة المحاولة بعد قليل."
                }, status_code=503)

            from services.sale_pricing import price_lines
            tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0), getattr(user, "custom_discount_pct", None))
            vol_disc_pct = BatStoreService.get_volume_discount(quantity)
            coupon_code = (body.get("coupon_code") or "").strip()
            coupon_type = coupon_value = None
            if coupon_code:
                from repositories.coupon import CouponRepository
                coupon = await CouponRepository.get_by_code(coupon_code, session)
                if coupon and coupon.is_active:
                    if not (coupon.usage_limit and coupon.usage_count >= coupon.usage_limit):
                        coupon_type, coupon_value = coupon.type, float(coupon.value or 0.0)
            try:
                (total_dec,), discount_limited = price_lines(
                    [(product.sell_price_usd, product.cost_usd, quantity, vol_disc_pct)],
                    discount_pct=discount_pct, coupon_type=coupon_type, coupon_value=coupon_value or 0,
                )
            except ValueError as e:
                if str(e) == "price_unavailable":
                    return JSONResponse({"error": "price_unavailable"}, status_code=400)
                raise
            total = float(total_dec)
            if coupon_code and coupon_type is not None:
                from repositories.coupon import CouponRepository
                coupon = await CouponRepository.get_by_code(coupon_code, session)
                if coupon and coupon.is_active:
                    await CouponRepository.increment_usage(coupon.id, session)

            # 1. Atomically debit customer balance
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

            # 2. Place upstream supplier order
            customer_ref = f"tma-{user.telegram_id}-{uuid.uuid4().hex[:8]}"
            try:
                placed = await MultiSupplierService.place_order_with_failover(
                    session, product, quantity,
                    customer_reference=customer_ref,
                    idempotency_key=customer_ref,
                )
                ext_ref = placed.get("external_order_ref")
                goods_list = placed.get("goods") or []
                supplier_used = placed.get("supplier") or getattr(product, "supplier", "batstore")
                server_badge = placed.get("server_badge") or getattr(product, "server_badge", "سيرفر 1 (BatStore)")
            except (BatStoreOutOfStockError, ProdSellerOutOfStockError) as e:
                logging.warning("Product #%s out of stock on all suppliers: %s", product.product_id, e)
                await UserRepository.refund_balance(user.telegram_id, total, session)
                product.stock = 0
                await BatStoreProductRepository.update(product, session)
                await session_commit(session)
                broadcast_sse_event("stock_update", {"product_id": product.product_id, "stock": 0})
                return JSONResponse({
                    "error": "out_of_stock",
                    "message": "نفد مخزون هذا المنتج مؤقتاً لدى المورد. تم استرداد المبلغ فوراً إلى رصيدك."
                }, status_code=409)
            except Exception as e:
                logging.error("Multi-supplier in-app checkout failed: %s", e)
                await UserRepository.refund_balance(user.telegram_id, total, session)
                await session_commit(session)
                return JSONResponse({"error": "supplier_failed", "message": str(e)}, status_code=502)

            # 3. Record order
            order_status = "completed" if product.delivery_type in ("stock", "supplier_api") else "pending_fulfillment"
            order = await BatStoreOrderRepository.create(BatStoreOrderDTO(
                telegram_id=user.telegram_id,
                total_sell=total,
                status=order_status,
                external_order_ref=str(ext_ref) if ext_ref else None,
                customer_reference=customer_ref,
                details=[{
                    "product_id": product.product_id,
                    "name": product.name,
                    "quantity": quantity,
                    "cost_usd": product.cost_usd,
                    "sell_usd": total,
                    "delivery_type": product.delivery_type,
                    "delivery_goods": goods_list,
                    "warranty_days": product.warranty_days or 0,
                    "supplier": supplier_used,
                    "server_badge": server_badge,
                }],
            ), session)
            await session_commit(session)

            # 4. Async notifications
            sym = config.CURRENCY.get_localized_symbol()
            await NotificationService.send_to_admins(
                f"🛒 <b>New In-App Mini App Order #{order.id}</b>\n\n"
                f"• <b>Customer:</b> tg:{user.telegram_id} (@{user.telegram_username or 'none'})\n"
                f"• <b>Item:</b> {quantity}× {product.name}\n"
                f"• <b>Total:</b> {total:.2f}{sym}\n"
                f"• <b>Status:</b> {order_status}",
                None
            )

            # Backup delivery into Telegram chat
            if goods_list:
                goods_lines = "\n".join(f"• <code>{g}</code>" for g in goods_list[:5])
                await NotificationService.send_to_user(
                    f"✅ <b>Order #{order.id} Successful!</b>\n\n"
                    f"📦 <b>Delivered Goods:</b>\n{goods_lines}\n\n"
                    "<i>(Tap any credential above to copy it)</i>",
                    user.telegram_id
                )

            # 5. Process 0.2% referral commission from margin
            if getattr(user, "referred_by_user_id", None):
                try:
                    referrer = await UserRepository.get_by_id(user.referred_by_user_id, session)
                    if referrer:
                        cost_total = (product.cost_usd or 0.0) * quantity
                        margin_profit = max(0.0, total - cost_total)
                        if margin_profit > 0:
                            ref_rate = float(os.environ.get("REFERRAL_MARGIN_COMMISSION_PERCENT", "0.2")) / 100.0
                            commission = round(margin_profit * ref_rate, 2)
                            if commission < 0.01:
                                commission = 0.01

                            await UserRepository.refund_balance(referrer.telegram_id, commission, session)
                            from repositories.referral import ReferralRepository
                            from models.referral import ReferralBonusDTO
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
                                    f"🎁 <b>أرباح إحالة جديدة!</b>\n\n"
                                    f"قام صديقك المدعو بعملية شراء ({product.name}) وتمت إضافة <b>+${commission:.2f}</b> كعمولة إلى رصيدك مباشرة!",
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
                "sym": sym,
                "goods": goods_list,
                "delivery_type": product.delivery_type or "stock",
                "warranty_days": product.warranty_days or 0
            }
    finally:
        try:
            await lock.release()
        except Exception:
            pass


@app.post("/api/cart/checkout")
async def tma_cart_checkout(request: Request):
    """Atomic multi-item checkout for the Telegram Mini App Cart Drawer."""
    import uuid
    from models.batstore_order import BatStoreOrderDTO
    from services.user import get_vip_tier_info

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    from services.telegram_auth import extract_and_verify_telegram_user
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

            from services.sale_pricing import price_lines
            cart_products = []
            price_inputs = []
            total_cart_cost = 0.0
            for it in items_input:
                pid = int(it.get("product_id") or 0)
                qty = max(1, min(20, int(it.get("quantity") or 1)))
                prod = await BatStoreProductRepository.get_by_product_id(pid, session)
                if not prod or prod.hidden:
                    return JSONResponse({"error": f"Product #{pid} is unavailable"}, status_code=400)
                cart_products.append({"product": prod, "quantity": qty})
                price_inputs.append((prod.sell_price_usd, prod.cost_usd, qty,
                                    BatStoreService.get_volume_discount(qty)))
                total_cart_cost += (prod.cost_usd or 0.0) * qty

            # Reseller Balance Circuit Breaker
            reseller_bal = await BatStoreService.get_cached_reseller_balance(session, redis)
            if reseller_bal < total_cart_cost:
                return JSONResponse({
                    "error": "supplier_replenishing",
                    "message": "المتجر يقوم حالياً بإعادة شحن الرصيد لدى المورد. يرجى إعادة المحاولة بعد قليل."
                }, status_code=503)

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
            from services.batstore import BatStoreOutOfStockError
            for cp in cart_products:
                prod = cp["product"]
                qty = cp["quantity"]
                cust_ref = f"cart-{user.telegram_id}-{uuid.uuid4().hex[:8]}"
                goods_list = []
                from services.multi_supplier import MultiSupplierService
                from services.prodseller import ProdSellerOutOfStockError
                supplier_used = getattr(prod, "supplier", "batstore")
                server_badge = getattr(prod, "server_badge", "⚡ سيرفر 1 (BatStore)")
                try:
                    placed = await MultiSupplierService.place_order_with_failover(
                        session, prod, qty,
                        customer_reference=cust_ref,
                        idempotency_key=cust_ref,
                    )
                    goods_list = placed.get("goods") or []
                    supplier_used = placed.get("supplier") or supplier_used
                    server_badge = placed.get("server_badge") or server_badge
                    all_goods.extend(goods_list)
                except (BatStoreOutOfStockError, ProdSellerOutOfStockError) as e:
                    logging.warning("Cart product #%s out of stock upstream: %s", prod.product_id, e)
                    prod.stock = 0
                    await BatStoreProductRepository.update(prod, session)
                    await session_commit(session)
                    broadcast_sse_event("stock_update", {"product_id": prod.product_id, "stock": 0})
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
                    "warranty_days": prod.warranty_days or 0,
                    "supplier": supplier_used,
                    "server_badge": server_badge,
                })

            order = await BatStoreOrderRepository.create(BatStoreOrderDTO(
                telegram_id=user.telegram_id,
                total_sell=total,
                status="completed",
                customer_reference=f"cart-{uuid.uuid4().hex[:10]}",
                details=order_details
            ), session)
            await session_commit(session)

            # Clear abandoned cart in Redis if synced
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


@app.post("/api/cart/checkout")
async def tma_cart_checkout(request: Request):
    """Atomic multi-item checkout for the Telegram Mini App Cart Drawer."""
    import uuid
    from models.batstore_order import BatStoreOrderDTO
    from services.user import get_vip_tier_info

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = int(body.get("tg_id") or 0)
    items_input = body.get("items") or []
    if not tg_id or not items_input:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        from services.sale_pricing import price_lines
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
                placed = await BatStoreService.place_order(
                    session, prod.product_id, qty,
                    customer_reference=cust_ref,
                    idempotency_key=cust_ref
                )
                items = placed.get("order", {}).get("items") or []
                goods_list = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
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

        sym = config.CURRENCY.get_localized_symbol()
        return {
            "status": "success",
            "order_id": order.id,
            "total_paid": total,
            "sym": sym,
            "goods": all_goods,
            "items_count": len(cart_products)
        }

@app.post("/api/admin/manual-sale")
async def admin_manual_sale(request: Request):
    """Admin-recorded externally paid sale at regular list price.

    No VIP/volume/coupon reductions and no wallet debit: the customer paid
    outside the store balance (cash, transfer). Historical zero-price gifts
    are left untouched; new manual sales record real revenue and unit cost.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_tg_id = int(body.get("admin_tg_id") or 0)
    if admin_tg_id not in config.ADMIN_ID_LIST:
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
        from repositories.batstore_product import BatStoreProductRepository
        from repositories.batstore_order import BatStoreOrderRepository
        from models.batstore_order import BatStoreOrderDTO
        from services.batstore import BatStoreService

        prod = await BatStoreProductRepository.get_by_product_id(product_id, session)
        if not prod:
            return JSONResponse({"error": "product_not_found"}, status_code=404)
        recipient = await UserRepository.get_by_tgid(target_tg_id, session)
        if not recipient:
            return JSONResponse({"error": "recipient_not_found"}, status_code=404)

        from decimal import Decimal, ROUND_HALF_UP
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
            "payment_method": "external",
            "sold_by": admin_tg_id,
        }]

        order = await BatStoreOrderRepository.create(BatStoreOrderDTO(
            telegram_id=target_tg_id,
            total_sell=total,
            status=order_status,
            external_order_ref=str(external_ref) if external_ref else None,
            customer_reference=cust_ref,
            details=order_details
        ), session)
        await session_commit(session)

        if target_tg_id != admin_tg_id and goods_list:
            try:
                credentials_text = "\n".join(f"<code>{g}</code>" for g in goods_list)
                sale_msg = (
                    f"✅ <b>تم تسليم طلبك من إدارة المتجر!</b>\n\n"
                    f"تم تسليمك: <b>{prod.name}</b> (الكمية: {qty})\n"
                    f"الإجمالي المدفوع خارج المتجر: <b>${total:.2f}</b>\n\n"
                    f"<b>بيانات الحساب / المفتاح:</b>\n{credentials_text}\n\n"
                    f"شكراً لتسوقك معنا في GH Store! 🛍️"
                )
                await bot.send_message(chat_id=target_tg_id, text=sale_msg, parse_mode="HTML")
            except Exception as e:
                logging.warning("Could not send manual-sale DM to user %s: %s", target_tg_id, e)

        return {
            "status": "success",
            "order_id": order.id,
            "target_tg_id": target_tg_id,
            "goods": goods_list,
            "product_name": prod.name,
            "quantity": qty,
            "total_sell": total,
            "order_status": order_status,
        }


@app.post("/api/admin/free-order")
async def admin_free_order(request: Request):
    """Retired zero-price gift route: manual sales are paid externally now."""
    return JSONResponse({"error": "manual_sale_required"}, status_code=410)

@app.post("/api/warranty/claim")
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


@app.post("/api/admin/warranty/replace")
async def admin_dispatch_warranty_replacement(request: Request):
    """Admin 1-click warranty replacement dispatch.
    Places a fresh upstream replacement, attaches delivered credentials,
    marks warranty fulfilled, and notifies the customer via Telegram bot DM.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id, request):
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

        import uuid
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
                    f"🔄 <b>تم تسليم بديل الضمان لطلبك #{order.id} بنجاح!</b>\n\n"
                    f"📦 <b>المنتج:</b> {pname}\n"
                    f"🔑 <b>بيانات الحساب / المفتاح البديل:</b>\n{cred_lines}\n\n"
                    f"<i>(انقر على أي مفتاح أعلاه لنسخه مباشرة)</i>\n\n"
                    f"شكراً لتسوقك معنا في GH Store! 🛡️"
                )
                await bot.send_message(chat_id=order.telegram_id, text=msg, parse_mode="HTML")
            except Exception as e:
                logging.warning("Could not send warranty replacement DM to user %s: %s", order.telegram_id, e)

        return {
            "status": "success",
            "order_id": order.id,
            "goods": goods_list,
            "message": "تم تسليم بديل الضمان وإرسال البيانات للعميل بنجاح!"
        }


@app.get("/api/admin/reports/export")
async def admin_export_accounting_ledger(request: Request, tg_id: int, start_date: str = "", end_date: str = ""):
    """Export accounting CSV ledger of orders and gross profit for reconciliation."""
    if not _verify_admin(tg_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    import io
    import csv
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    from models.batstore_order import BatStoreOrder
    from models.user import User

    now = _dt.now(_tz.utc)
    since = now - _td(days=30)
    until = now + _td(days=1)

    if start_date:
        try:
            since = _dt.fromisoformat(start_date).replace(tzinfo=_tz.utc)
        except Exception:
            pass
    if end_date:
        try:
            until = _dt.fromisoformat(end_date).replace(tzinfo=_tz.utc)
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

        from services.sale_pricing import order_cost, externally_paid
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
        from fastapi.responses import Response
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@app.post("/api/cart/sync")
async def tma_cart_sync(request: Request):
    """Sync client-side TMA cart to Redis for abandoned cart recovery notifications."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    from services.telegram_auth import extract_and_verify_telegram_user
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

    import time as _time
    import json as _json
    cart_data = {
        "tg_id": tg_id,
        "items": items,
        "updated_at": _time.time()
    }
    try:
        await redis.setex(key, 604800, _json.dumps(cart_data))
    except Exception as e:
        logging.warning("Failed to sync TMA cart to Redis: %s", e)
    return {"status": "synced", "items_count": len(items)}


@app.post("/api/search/log")
async def log_search_query(request: Request):
    """Increment search term frequency in Redis sorted set for real-time trending."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored"}
    q = str(body.get("query") or "").strip().lower()
    if not q or len(q) < 2 or len(q) > 40:
        return {"status": "ignored"}
    try:
        await redis.zincrby("ghstore:search_trends", 1, q)
        await redis.expire("ghstore:search_trends", 172800)
    except Exception as e:
        logging.debug("Failed to log search query: %s", e)
    return {"status": "logged"}


@app.get("/api/search/trending")
async def get_trending_searches():
    """Return top 6 real-time trending searches from Redis with fallback."""
    fallback = ["ChatGPT", "Claude", "Gemini", "Peacock", "Windows", "Canva"]
    try:
        raw_items = await redis.zrevrange("ghstore:search_trends", 0, 5)
        if raw_items:
            terms = [k.decode() if isinstance(k, bytes) else str(k) for k in raw_items]
            cleaned = [t.title() if len(t) > 3 else t.upper() for t in terms if t]
            if len(cleaned) >= 3:
                return {"trending": cleaned}
    except Exception as e:
        logging.debug("Failed to fetch trending searches: %s", e)
    return {"trending": fallback}


@app.post("/api/admin/flash-sale/update")
async def admin_update_flash_sale(request: Request):
    """Admin updates store flash sale status and countdown duration."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    enabled = "true" if body.get("enabled") else "false"
    pct = str(float(body.get("percent") or 15.0))
    duration_hours = int(body.get("duration_hours") or 24)
    import time as _t
    end_ts = str(int(_t.time()) + (duration_hours * 3600)) if enabled == "true" else "0"
    async with get_db_session() as session:
        await ConfigService.set(session, "FLASH_SALE_ENABLED", enabled)
        await ConfigService.set(session, "FLASH_SALE_PERCENT", pct)
        await ConfigService.set(session, "FLASH_SALE_END_TIMESTAMP", end_ts)
        await session_commit(session)
    return {"status": "ok", "enabled": enabled == "true", "end_timestamp": int(end_ts)}


@app.post("/api/support/ticket")
async def submit_support_ticket(request: Request):
    """In-app customer support inquiry dispatched to admin Telegram topic."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    from services.telegram_auth import extract_and_verify_telegram_user
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
        import time as _t
        ticket_id = int(_t.time()) % 100000
        ticket_card = (
            f"🎫 <b>تذكرة دعم فني جديدة #{ticket_id}</b>\n\n"
            f"• <b>العميل:</b> {username_str} (<code>{tg_id}</code>)\n"
            f"• <b>الطلب المتعلق:</b> #{order_id or 'لا يوجد'}\n"
            f"• <b>الموضوع:</b> {subject}\n\n"
            f"📝 <b>نص الرسالة:</b>\n{message}"
        )
        await NotificationService.send_to_admins(ticket_card, None)
    return {"status": "success", "ticket_id": ticket_id}


async def _run_admin_broadcast(broadcast_id: str, message: str, target_segment: str):
    """Rate-limited background broadcast runner (~25 msgs/sec)."""
    try:
        async with get_db_session() as session:
            from models.user import User
            from sqlalchemy import select
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
                await asyncio.sleep(0.04)  # ~25 msg/sec to respect Telegram limits

                # Update progress every 20 messages
                if (sent + failed) % 20 == 0:
                    try:
                        import json as _j
                        await redis.setex(
                            f"ghstore:broadcast:{broadcast_id}",
                            3600,
                            _j.dumps({"total": total, "sent": sent, "failed": failed, "active": True})
                        )
                    except Exception:
                        pass

            # Completed
            import json as _j
            await redis.setex(
                f"ghstore:broadcast:{broadcast_id}",
                7200,
                _j.dumps({"total": total, "sent": sent, "failed": failed, "active": False})
            )
    except Exception as e:
        logging.error("Broadcast %s failed: %s", broadcast_id, e)


@app.post("/api/admin/broadcast")
async def admin_start_broadcast(request: Request):
    """Admin starts an asynchronous rate-limited Telegram broadcast."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    msg = str(body.get("message") or "").strip()
    segment = str(body.get("target_segment") or "all").strip().lower()
    if not msg:
        return JSONResponse({"error": "empty_message"}, status_code=400)

    import uuid as _u
    broadcast_id = _u.uuid4().hex[:8]
    asyncio.create_task(_run_admin_broadcast(broadcast_id, msg, segment))
    return {"status": "started", "broadcast_id": broadcast_id}


@app.get("/api/admin/broadcast/status")
async def admin_broadcast_status(request: Request, tg_id: int, broadcast_id: str):
    """Check live status and delivery metrics of an active broadcast."""
    if not _verify_admin(tg_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    try:
        import json as _j
        raw = await redis.get(f"ghstore:broadcast:{broadcast_id}")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return {"active": False, "sent": 0, "total": 0, "failed": 0}


@app.post("/api/invoice/stars")
async def create_tma_stars_invoice(request: Request):
    """Generate a Telegram Stars invoice link for direct in-app Mini App checkout."""
    body = await request.json()
    tg_id = int(body.get("tg_id") or 0)
    product_id = int(body.get("product_id") or 0)
    qty = max(1, min(10, int(body.get("quantity") or 1)))

    if not tg_id or not product_id:
        return JSONResponse({"error": "missing_params"}, status_code=400)

    async with get_db_session() as session:
        product = await BatStoreProductRepository.get_by_product_id(product_id, session)
        if not product:
            return JSONResponse({"error": "product_not_found"}, status_code=404)

        user = await UserRepository.get_by_tgid(tg_id, session)
        from services.user import get_vip_tier_info
        from services.sale_pricing import price_lines
        tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0), getattr(user, "custom_discount_pct", None))
        try:
            (total_dec,), _ = price_lines(
                [(product.sell_price_usd, product.cost_usd, qty, 0)],
                discount_pct=discount_pct)
        except ValueError:
            return JSONResponse({"error": "price_unavailable"}, status_code=400)
        total_usd = float(total_dec)

        stars_rate = float(config.GHSTORE_STARS_TO_USD or 0.01)
        stars = max(1, int(total_usd / stars_rate))

        from aiogram.types import LabeledPrice
        title = f"{product.name[:32]}"
        description = f"{qty}x {product.name} — Direct Stars Checkout"
        payload = f"stars_inapp:{tg_id}:{product_id}:{qty}:{stars}:{total_usd}"

        try:
            invoice_link = await bot.create_invoice_link(
                title=title,
                description=description,
                payload=payload,
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=f"{stars} ⭐", amount=stars)],
            )
            return {"status": "ok", "invoice_link": invoice_link, "stars": stars, "total_usd": total_usd}
        except Exception as e:
            logging.error("Failed to generate Stars invoice link: %s", e)
            return JSONResponse({"error": "invoice_creation_failed", "detail": str(e)}, status_code=502)


@app.post("/api/invoice/topup")
async def create_tma_topup_invoice(request: Request):
    """Generate in-app top-up invoice or payment link for Stars, Crypto, or SAM."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = int(body.get("tg_id") or 0)
    amount = float(body.get("amount") or 10.0)
    method = (body.get("method") or "stars").lower()

    if not tg_id or amount <= 0:
        return JSONResponse({"error": "invalid_params"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        if method == "stars":
            stars_rate = float(config.GHSTORE_STARS_TO_USD or 0.01)
            stars = max(1, int(amount / stars_rate))
            from aiogram.types import LabeledPrice
            title = f"GH Store ${amount:.2f} Top-up"
            description = f"Add ${amount:.2f} USD to your spendable bot balance"
            payload = f"stars_topup:{tg_id}:{stars}:{amount:.2f}"

            try:
                invoice_link = await bot.create_invoice_link(
                    title=title,
                    description=description,
                    payload=payload,
                    provider_token="",
                    currency="XTR",
                    prices=[LabeledPrice(label=f"{stars} ⭐", amount=stars)],
                )
                return {"status": "ok", "type": "stars", "invoice_link": invoice_link, "stars": stars, "amount": amount}
            except Exception as e:
                logging.error("Failed to generate Stars top-up invoice: %s", e)
                return JSONResponse({"error": "invoice_failed", "detail": str(e)}, status_code=502)

        elif method in ("crypto", "bep20", "usdt", "usdt_bep20"):
            try:
                from crypto_api.CryptoApiWrapper import CryptoApiWrapper
                from enums.currency import Currency
                from enums.cryptocurrency import Cryptocurrency
                from models.payment import PaymentType, ProcessingPaymentDTO
                payment = await CryptoApiWrapper.create_invoice(ProcessingPaymentDTO(
                    paymentType=PaymentType.PAYMENT,
                    fiatCurrency=Currency.USD,
                    fiatAmount=amount,
                    cryptoCurrency=Cryptocurrency.USDT_BEP20,
                    callbackUrl=f"{(config.WEBHOOK_HOST or '').rstrip('/')}{config.WEBHOOK_PATH}cryptoprocessing/event",
                    callbackSecret="secret",
                ))
                inv_uuid = str(uuid.uuid4().hex[:10])
                pay_url = getattr(payment, "paymentUrl", None) or ""
                addr = getattr(payment, "address", None) or ""
                final_url = pay_url if pay_url else (f"https://bscscan.com/address/{addr}" if addr else "")
                return {
                    "status": "ok",
                    "type": "url",
                    "provider": "crypto",
                    "url": final_url,
                    "address": addr,
                    "invoice_id": str(getattr(payment, "id", "") or inv_uuid),
                    "amount": amount,
                    "currency": "USDT (BEP-20)",
                    "network": "BEP-20 (Binance Smart Chain)",
                }
            except Exception as e:
                logging.error("Failed to create crypto invoice: %s", e)
                return JSONResponse({"error": "crypto_failed", "detail": str(e)}, status_code=502)
        elif method in ("sam", "shamcash", "syriatelcash", "syriatel"):
            provider = "syriatelcash" if method in ("syriatelcash", "syriatel") or body.get("provider") in ("syriatel", "syriatelcash") else "shamcash"
            try:
                from services.sam import SamService
                req_currency = (body.get("currency") or ("SYP" if provider == "syriatelcash" else "USD")).upper()
                if provider == "syriatelcash" or req_currency == "SYP":
                    inv_currency = "SYP"
                    syp_cfg = await ConfigService.get(session, "SAM_SYP_USD_RATE", env_fallback=os.environ.get("SAM_SYP_USD_RATE", "0.002551"))
                    syp_rate = float(syp_cfg or 0.002551)
                    syp_amount = int(round(amount / syp_rate)) if syp_rate < 1.0 else int(round(amount * syp_rate))
                    inv_amount = syp_amount
                else:
                    inv_currency = "USD"
                    inv_amount = amount

                invoice = await SamService.create_invoice(
                    session=session,
                    method=provider,
                    amount=inv_amount,
                    currency=inv_currency,
                    webhook_url=config.get_sam_webhook_url()
                )

                invoice_id = invoice.get("invoiceId")
                if invoice_id:
                    from repositories.sam_payment import SamPaymentRepository
                    from models.sam_payment import SamPaymentDTO
                    await SamPaymentRepository.create(SamPaymentDTO(
                        telegram_id=tg_id,
                        method=provider,
                        amount=float(inv_amount),
                        currency=inv_currency,
                        usd_amount=float(amount),
                        invoice_id=str(invoice_id),
                        payment_url=invoice.get("paymentUrl"),
                        event="pending"
                    ), session)
                    await session_commit(session)

                return {
                    "status": "ok",
                    "type": "url",
                    "url": invoice.get("paymentUrl"),
                    "invoice_id": str(invoice_id or ""),
                    "provider": provider,
                    "amount": amount,
                    "invoice_amount": inv_amount,
                    "currency": inv_currency
                }
            except Exception as e:
                err_str = str(e)
                logging.error("Failed to create invoice for provider %s: %s", provider, e)
                if "NOT_FOUND" in err_str or "المحفظة غير موجودة" in err_str:
                    user_msg = "بوابة سيرياتيل كاش قيد الصيانة حالياً. يرجى استخدام شام كاش أو نجوم تيليجرام أو العملات الرقمية." if provider == "syriatelcash" else "محفظة شام كاش غير متوفرة حالياً. يرجى تجربة طريقة شحن أخرى."
                    return JSONResponse({"status": "error", "error": user_msg}, status_code=400)
                return JSONResponse({"status": "error", "error": "تعذر إنشاء فاتورة الشحن حالياً. يرجى إعادة المحاولة.", "detail": err_str}, status_code=502)
    return JSONResponse({"error": "unknown_method"}, status_code=400)


@app.post("/api/invoice/check")
async def check_tma_invoice(request: Request):
    """Check payment status of a top-up invoice in real-time and refresh user balance."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = int(body.get("tg_id") or 0)
    invoice_id = str(body.get("invoice_id") or "").strip()
    method = str(body.get("method") or "").lower()

    if not tg_id:
        return JSONResponse({"error": "missing_tg_id"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        is_paid = False
        credited_now = False

        if invoice_id and method in ("sam", "shamcash", "syriatelcash", "syriatel"):
            try:
                from services.sam import SamService
                from repositories.sam_payment import SamPaymentRepository
                from services.referral import ReferralService
                payment = await SamPaymentRepository.get_by_invoice_id(invoice_id, session)
                if payment:
                    if payment.event == "invoice.paid":
                        is_paid = True
                    else:
                        status_info = await SamService.get_invoice(session, invoice_id)
                        upstream_status = (status_info.get("status") or "").lower()
                        if upstream_status == "paid":
                            is_paid = True
                            credited_now = True
                            await ReferralService.apply_deposit_referral(payment.usd_amount, user, session)
                            await SamPaymentRepository.mark_event(invoice_id, "invoice.paid", status_info.get("transactionRef"), session)
                            await session_commit(session)
            except Exception as e:
                logging.warning("Failed to check SAM invoice %s: %s", invoice_id, e)

        current_balance = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
        curr_pref = getattr(user, "currency_preference", "USD") or "USD"
        from services.user import format_currency_display

        msg = "تم تأكيد الدفع وإضافة الرصيد بنجاح! 🎉" if is_paid else "الفاتورة بانتظار الدفع أو التحويل."
        return {
            "status": "paid" if is_paid else "pending",
            "is_paid": is_paid,
            "credited_now": credited_now,
            "balance": current_balance,
            "display_balance": format_currency_display(current_balance, curr_pref),
            "message": msg
        }


@app.post("/api/restock/subscribe")
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


@app.post("/api/coupon/validate")
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
    from enums.coupon_type import CouponType
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


@app.post("/api/price-quote")
async def tma_price_quote(request: Request):
    """Authoritative cost-floored quote shared by checkout; never exposes supplier costs."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    from services.telegram_auth import extract_and_verify_telegram_user
    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)
    items_input = body.get("items") or []
    if not tg_id or not items_input:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)
    from services.sale_pricing import price_lines
    from services.user import get_vip_tier_info
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


@app.post("/api/voucher/redeem")
async def tma_redeem_voucher(request: Request):
    """Redeem a prepaid digital gift voucher code."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = int(body.get("tg_id") or 0)
    code = (body.get("code") or "").strip()

    if not tg_id or not code:
        return JSONResponse({"error": "missing_code_or_id"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        success, amount, msg = await GiftVoucherRepository.redeem(code, user.id, session)
        if not success:
            return JSONResponse({"error": msg}, status_code=400)

        await session_commit(session)
        user_updated = await UserRepository.get_by_tgid(tg_id, session)
        new_bal = round((user_updated.top_up_amount or 0.0) - (user_updated.consume_records or 0.0), 2)
        sym = config.CURRENCY.get_localized_symbol()

    return {
        "status": "success",
        "amount": amount,
        "new_balance": new_bal,
        "message": f"Successfully credited {amount:.2f}{sym} to your balance!",
    }



def _verify_admin(tg_id: int | None, request: Request | None = None) -> bool:
    if not tg_id:
        return False
    if request is not None:
        from services.telegram_auth import extract_and_verify_telegram_user
        try:
            tg_id = extract_and_verify_telegram_user(request, int(tg_id))
        except Exception:
            return False
    return int(tg_id) in config.ADMIN_ID_LIST


@app.post("/api/admin/rate/update")
async def admin_update_rate(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    rate_raw = float(body.get("syp_rate") or 0.0)
    if rate_raw <= 0:
        return JSONResponse({"error": "invalid_rate"}, status_code=400)
    usd_rate = (1.0 / rate_raw) if rate_raw > 100.0 else rate_raw
    async with get_db_session() as session:
        await ConfigService.set(session, "SAM_SYP_USD_RATE", f"{usd_rate:.8f}")
        await session_commit(session)
    from services.currency_rates import CurrencyRateService
    CurrencyRateService._rates["SYP"] = float(rate_raw if rate_raw > 100.0 else round(1.0 / rate_raw, 2))
    return {"status": "ok", "syp_rate": int(round(rate_raw if rate_raw > 100.0 else 1.0 / rate_raw))}


@app.post("/api/admin/referral-rate/update")
async def admin_update_referral_rate(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    ref_rate = float(body.get("referral_rate") or 0.2)
    async with get_db_session() as session:
        await ConfigService.set(session, "REFERRAL_MARGIN_COMMISSION_PERCENT", str(ref_rate))
        await session_commit(session)
    return {"status": "ok", "referral_rate": ref_rate}


@app.post("/api/admin/store-logo/update")
async def admin_update_store_logo(request: Request):
    """Update the store logo URL in PostgreSQL app_config."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    logo_url = (body.get("logo_url") or "").strip()
    async with get_db_session() as session:
        await ConfigService.set(session, "STORE_LOGO_URL", logo_url)
        await session_commit(session)
    return {"status": "ok", "store_logo_url": logo_url}


@app.post("/api/admin/margin/update")
async def admin_update_margin(request: Request):
    """Update global profit margin percentage on reseller products."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    margin_val = float(body.get("margin_percent") or 20.0)
    async with get_db_session() as session:
        await ConfigService.set(session, "GLOBAL_MARGIN_PERCENT", str(margin_val))
        await session_commit(session)
    return {"status": "ok", "margin_percent": margin_val}


@app.post("/api/admin/stars-rate/update")
async def admin_update_stars_rate(request: Request):
    """Update Telegram Stars to USD conversion rate."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    rate_val = float(body.get("stars_rate") or 0.01)
    async with get_db_session() as session:
        await ConfigService.set(session, "GHSTORE_STARS_TO_USD", str(rate_val))
        await session_commit(session)
    return {"status": "ok", "stars_rate": rate_val}


@app.post("/api/admin/announcement/update")
async def admin_update_announcement(request: Request):
    """Update broadcast store announcement message."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    announcement = (body.get("announcement") or "").strip()
    async with get_db_session() as session:
        await ConfigService.set(session, "STORE_ANNOUNCEMENT", announcement)
        await session_commit(session)
    return {"status": "ok", "announcement": announcement}


@app.post("/api/admin/catalog/sync")
async def admin_sync_catalog(request: Request):
    """Force an immediate background sync of the BatStore supplier catalog."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        from services.batstore import BatStoreService
        created, updated = await BatStoreService.sync_catalog(session)
        await session_commit(session)
    return {
        "status": "ok",
        "created": created,
        "updated": updated,
        "message": f"تمت مزامنة الكتالوج بنجاح! تم إنشاء {created} وتحديث {updated} منتج."
    }


@app.post("/api/admin/autorefund/toggle")
async def admin_toggle_autorefund(request: Request):
    """Toggle automated refund mode (enabled vs manual)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        curr = await ConfigService.get(session, "AUTOREFUND_ENABLED", default="false")
        new_val = "false" if (curr or "").lower() in ("true", "1", "yes") else "true"
        await ConfigService.set(session, "AUTOREFUND_ENABLED", new_val)
        await session_commit(session)
    return {"status": "ok", "autorefund_enabled": new_val == "true"}


@app.get("/api/admin/stuck-orders")
async def admin_get_stuck_orders(tg_id: int):
    """Return orders that are pending fulfillment or stuck requiring admin action."""
    if not _verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        from models.batstore_order import BatStoreOrder
        from models.user import User

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

@app.get("/api/admin/live-activity")
async def admin_get_live_activity(tg_id: int, limit: int = 50):
    """Real-time store activity radar for admin: live stream of all customer orders & recharges."""
    if not _verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    async with get_db_session() as session:
        from models.batstore_order import BatStoreOrder
        from models.sam_payment import SamPayment
        from models.stars_payment import StarsPayment
        from models.user import User

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

        # 2. SAM Recharges (ShamCash & SyriatelCash)
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
                "method": sp.method or "shamcash",
                "title": f"شحن {sp.method.upper() if sp.method else 'SAM'}",
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


@app.post("/api/admin/recharge/approve")
async def admin_approve_recharge(request: Request):
    """Admin manually approves a failed or pending recharge, credits customer balance, and sends Telegram alert."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_tg_id = int(body.get("admin_tg_id") or 0)
    if not _verify_admin(admin_tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    recharge_id = str(body.get("recharge_id") or "")
    target_tg_id = int(body.get("telegram_id") or 0)
    amount_usd = float(body.get("amount_usd") or 0.0)
    async with get_db_session() as session:
        if not target_tg_id and recharge_id.startswith("sam_"):
            try:
                raw_sam_id = int(recharge_id.replace("sam_", ""))
                from models.sam_payment import SamPayment
                sp_check = (await session_execute(select(SamPayment).where(SamPayment.id == raw_sam_id), session)).scalar_one_or_none()
                if sp_check:
                    target_tg_id = sp_check.telegram_id
                    if amount_usd <= 0:
                        amount_usd = float(sp_check.usd_amount or 0.0)
            except Exception:
                pass

        if not target_tg_id or amount_usd <= 0:
            return JSONResponse({"error": "invalid_params"}, status_code=400)

        from sqlalchemy import update as _sql_update, func as _sql_func
        from models.user import User as _UserModel
        res = await session_execute(
            _sql_update(_UserModel)
            .where(_UserModel.telegram_id == target_tg_id)
            .values(top_up_amount=_sql_func.coalesce(_UserModel.top_up_amount, 0.0) + amount_usd)
            .returning(_UserModel.top_up_amount, _UserModel.consume_records),
            session
        )
        row = res.first()
        if not row:
            return JSONResponse({"error": "user_not_found"}, status_code=404)
        new_topup, consume = row
        new_balance = round(float(new_topup or 0.0) - float(consume or 0.0), 2)
        # Update record if it's SAM payment
        if recharge_id.startswith("sam_"):
            raw_sam_id = int(recharge_id.replace("sam_", ""))
            from models.sam_payment import SamPayment
            sp = (await session_execute(select(SamPayment).where(SamPayment.id == raw_sam_id), session)).scalar_one_or_none()
            if sp:
                sp.event = "invoice.paid"

        # Log in Admin Audit Log
        from models.admin_audit_log import AdminAuditLog
        session.add(AdminAuditLog(
            admin_tg_id=admin_tg_id,
            action="recharge_approved",
            details={"target_user": target_tg_id, "amount_usd": amount_usd, "recharge_id": recharge_id}
        ))
        await session_commit(session)

        # Send celebration Telegram notification to customer
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


@app.post("/api/admin/stuck-orders/refund")
async def admin_refund_stuck_order(request: Request):
    """Admin manually refunds a stuck order, crediting user balance and notifying them."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
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

        from services.sale_pricing import externally_paid
        refund_amount = round(float(order.total_sell or 0.0), 2)
        wallet_credited = False
        user = await UserRepository.get_by_tgid(order.telegram_id, session)
        if user and not externally_paid(order):
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

    return {"status": "ok", "refunded_amount": refund_amount if wallet_credited else 0.0, "order_id": order_id, "wallet_credited": wallet_credited}


@app.post("/api/admin/prodseller/test-balance")
async def admin_test_prodseller_balance(request: Request):
    """Test ProdSeller API key live and return real-time balance and membership tier."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    api_key = str(body.get("api_key") or "").strip()
    from services.prodseller import ProdSellerService
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


@app.post("/api/admin/batstore/test-balance")
async def admin_test_batstore_balance(request: Request):
    """Test BatStore API key live and return real-time balance and user status."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    api_key = str(body.get("api_key") or "").strip()
    from services.batstore import BatStoreService
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


@app.get("/api/admin/supplier/details")
async def admin_get_supplier_details(tg_id: int):
    """Return paired supplier settings, status, and config for the dedicated admin suppliers page."""
    if not _verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        bat_key = await ConfigService.get(session, "BATSTORE_API_KEY", env_fallback=os.environ.get("BATSTORE_API_KEY", ""))
        prod_key = await ConfigService.get(session, "PRODSELLER_API_KEY", env_fallback=os.environ.get("PRODSELLER_API_KEY", ""))
        strategy = await ConfigService.get(session, "SUPPLIER_ROUTING_STRATEGY", default="auto_cheapest")
        bat_sync = (await ConfigService.get(session, "BATSTORE_SYNC_ENABLED", default="true")).lower() == "true"
        prod_sync = (await ConfigService.get(session, "PRODSELLER_SYNC_ENABLED", default="true")).lower() == "true"
        auto_failover = (await ConfigService.get(session, "SUPPLIER_AUTO_FAILOVER", default="true")).lower() == "true"

        from models.batstore_product import BatStoreProduct
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


@app.post("/api/admin/supplier/config")
async def admin_update_supplier_config(request: Request):
    """Save paired supplier keys, sync preferences, and routing strategy to database."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id, request):
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

@app.post("/api/admin/supplier/sync")
async def admin_sync_all_suppliers(request: Request):
    """Trigger manual 1-tap catalog synchronization across all suppliers."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    async with get_db_session() as session:
        from services.multi_supplier import MultiSupplierService
        res = await MultiSupplierService.sync_all_suppliers(session)

    return {"status": "ok", "result": res}
@app.get("/api/admin/config/all")
async def admin_get_all_configs(tg_id: int):
    """Return all system configuration keys, current values, and descriptions."""
    if not _verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        from services.config import CONFIG_DEFINITIONS
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


@app.post("/api/admin/config/set")
async def admin_set_config(request: Request):
    """Update any system configuration key in PostgreSQL app_config."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    key = str(body.get("key") or "").strip()
    value = str(body.get("value") or "").strip()
    if not key:
        return JSONResponse({"error": "missing_key"}, status_code=400)
    async with get_db_session() as session:
        await ConfigService.set(session, key, value)
        await session_commit(session)
    return {"status": "ok", "key": key, "value": value}


@app.get("/api/admin/users")
async def admin_get_users(tg_id: int, query: str = ""):
    if not _verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        from models.user import User
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


@app.post("/api/admin/users/adjust-balance")
async def admin_adjust_balance(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
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
        else:
            # Admin deducting/removing balance:
            # Deduct from user.top_up_amount down to a minimum of user.consume_records (balance >= 0).
            # NEVER touch consume_records, which strictly represents actual customer purchases (المشتريات).
            current_top_up = user.top_up_amount or 0.0
            consumed = user.consume_records or 0.0
            current_bal = max(0.0, current_top_up - consumed)
            new_bal = max(0.0, current_bal - amount)
            user.top_up_amount = consumed + new_bal
        await UserRepository.update(user, session)
        from models.admin_audit_log import AdminAuditLog
        session.add(AdminAuditLog(
            admin_tg_id=int(admin_id),
            action="adjust_balance",
            details={"target_tg_id": target_tg_id, "amount": amount, "type": action_type},
            created_at=datetime.datetime.now(datetime.timezone.utc)
        ))
        await session_commit(session)
        try:
            sign = "+" if action_type == "add" else "-"
            await bot.send_message(
                target_tg_id,
                f"💳 <b>إشعار تعديل الرصيد من الإدارة:</b>\n"
                f"تم { 'إضافة' if action_type == 'add' else 'خصم' } <b>{sign}${amount:.2f}</b> { 'إلى' if action_type == 'add' else 'من' } رصيدك."
            )
        except Exception:
            pass
        new_bal = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
    return {"status": "ok", "new_balance": new_bal}


@app.post("/api/admin/users/toggle-ban")
async def admin_toggle_ban(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
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

@app.post("/api/admin/users/send-message")
async def admin_send_user_message(request: Request):
    """Admin sends direct message to a customer from the bot."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    target_tg_id = int(body.get("target_tg_id") or 0)
    msg_text = (body.get("message") or "").strip()
    if not target_tg_id or not msg_text:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)
    try:
        await bot.send_message(target_tg_id, f"📬 <b>رسالة من إدارة المتجر:</b>\n\n{msg_text}")
        return {"status": "ok", "message": "تم إرسال الرسالة للمستخدم بنجاح!"}
    except Exception as e:
        return JSONResponse({"error": "send_failed", "detail": str(e)}, status_code=502)


@app.post("/api/admin/users/set-discount")
async def admin_set_discount(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    target_tg_id = int(body.get("target_tg_id") or 0)
    disc_val = body.get("discount_pct")
    async with get_db_session() as session:
        from models.user import User
        stmt = select(User).where(User.telegram_id == target_tg_id)
        user_row = (await session_execute(stmt, session)).scalar_one_or_none()
        if not user_row:
            return JSONResponse({"error": "user_not_found"}, status_code=404)
        user_row.custom_discount_pct = float(disc_val) if (disc_val is not None and str(disc_val).strip() != "") else None
        await session_commit(session)
    return {"status": "ok", "custom_discount_pct": user_row.custom_discount_pct}


@app.get("/api/admin/orders")
async def admin_get_orders(tg_id: int, status: str = "all"):
    if not _verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        from models.batstore_order import BatStoreOrder
        from models.user import User
        stmt = (
            select(BatStoreOrder, User.telegram_username)
            .outerjoin(User, User.telegram_id == BatStoreOrder.telegram_id)
            .order_by(BatStoreOrder.id.desc())
            .limit(30)
        )
        if status != "all":
            stmt = stmt.where(BatStoreOrder.status == status)
        rows = (await session_execute(stmt, session)).all()
        orders_out = []
        for o, uname in rows:
            items_names = [d.get("name") or "Product" for d in (o.details or [])]
            goods = [str(g) for d in (o.details or []) for g in (d.get("delivery_goods") or [])]
            cost = sum(float(d.get("cost_usd") or 0.0) * float(d.get("quantity") or 1) for d in (o.details or []))
            gross_profit = round(float(o.total_sell or 0.0) - cost, 2)
            orders_out.append({
                "id": o.id,
                "telegram_id": o.telegram_id,
                "username": f"@{uname}" if uname else "",
                "status": o.status,
                "total_sell": round(float(o.total_sell or 0.0), 2),
                "cost_usd": round(cost, 2),
                "gross_profit": gross_profit,
                "margin": gross_profit,
                "products": ", ".join(items_names) if items_names else "Order",
                "goods": goods,
                "created_at": o.created_at.strftime("%b %d, %H:%M") if o.created_at else "",
                "external_order_ref": o.external_order_ref or ""
            })
    return {"orders": orders_out}


@app.post("/api/admin/orders/update-status")
async def admin_update_order_status(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    order_id = int(body.get("order_id") or 0)
    new_status = body.get("new_status")
    async with get_db_session() as session:
        from models.batstore_order import BatStoreOrder
        stmt = select(BatStoreOrder).where(BatStoreOrder.id == order_id)
        order = (await session_execute(stmt, session)).scalar_one_or_none()
        if not order:
            return JSONResponse({"error": "order_not_found"}, status_code=404)
        if new_status == "refunded" and order.status != "refunded":
            from services.sale_pricing import externally_paid as _externally_paid
            if not _externally_paid(order):
                await UserRepository.refund_balance(order.telegram_id, float(order.total_sell or 0.0), session)
            try:
                await bot.send_message(
                    order.telegram_id,
                    f"↩️ <b>تم استرداد قيمة الطلب #{order.id}:</b>\n"
                    f"تمت إعادة <b>+${order.total_sell:.2f}</b> إلى رصيدك في المتجر."
                )
            except Exception:
                pass
        order.status = new_status
        await session_commit(session)
    return {"status": "ok", "new_status": new_status}


@app.get("/api/admin/coupons")
async def admin_get_coupons(tg_id: int):
    if not _verify_admin(tg_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    async with get_db_session() as session:
        from models.coupon import Coupon
        stmt = select(Coupon).order_by(Coupon.id.desc()).limit(30)
        coupons = (await session_execute(stmt, session)).scalars().all()
        res = []
        for c in coupons:
            res.append({
                "id": c.id,
                "code": c.code,
                "type": c.type.value if hasattr(c.type, "value") else str(c.type),
                "value": float(c.value),
                "usage_limit": c.usage_limit,
                "usage_count": c.usage_count,
                "is_active": c.is_active,
                "expires_at": c.expire_datetime.strftime("%Y-%m-%d") if c.expire_datetime else ""
            })
    return {"coupons": res}


@app.post("/api/admin/coupons/create")
async def admin_create_coupon(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    code = (body.get("code") or "").strip().upper()
    val = float(body.get("value") or 10.0)
    c_type_str = body.get("type", "percent").lower()
    usage_limit = int(body.get("usage_limit") or 100)
    from enums.coupon_type import CouponType
    from models.coupon import CouponDTO
    c_type = CouponType.PERCENT if "percent" in c_type_str else CouponType.CURRENCY
    async with get_db_session() as session:
        from repositories.coupon import CouponRepository
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        exp_dt = now_dt + datetime.timedelta(days=90)
        c_dto = await CouponRepository.create(CouponDTO(
            code=code,
            type=c_type,
            value=val,
            create_datetime=now_dt,
            expire_datetime=exp_dt,
            is_active=True,
            usage_limit=usage_limit,
            usage_count=0
        ), session)
        await session_commit(session)
    return {"status": "ok", "coupon": {"id": c_dto.id, "code": c_dto.code}}


@app.post("/api/admin/coupons/toggle")
async def admin_toggle_coupon(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    coupon_id = int(body.get("coupon_id") or 0)
    async with get_db_session() as session:
        from models.coupon import Coupon
        stmt = select(Coupon).where(Coupon.id == coupon_id)
        coupon = (await session_execute(stmt, session)).scalar_one_or_none()
        if not coupon:
            return JSONResponse({"error": "coupon_not_found"}, status_code=404)
        coupon.is_active = not coupon.is_active
        await session_commit(session)
    return {"status": "ok", "is_active": coupon.is_active}


@app.post("/api/admin/product/update")
async def admin_update_product(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    product_id = int(body.get("product_id") or 0)
    async with get_db_session() as session:
        from models.batstore_product import BatStoreProduct
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
    return {"status": "ok", "product_id": product_id}


@app.post("/api/admin/category/update")
async def admin_update_category(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id):
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    category_id = int(body.get("category_id") or 0)
    async with get_db_session() as session:
        from models.storefront_category import StorefrontCategory
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
        if "sort_order" in body:
            cat.sort_order = int(body["sort_order"])
        if "hidden" in body:
            cat.hidden = bool(body["hidden"])
        await session_commit(session)
    return {"status": "ok", "category_id": category_id}

@app.post("/api/reviews/submit")
async def tma_submit_review(request: Request):
    """Submit customer star rating and review directly from the Mini App."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = int(body.get("tg_id") or 0)
    from services.telegram_auth import extract_and_verify_telegram_user
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
        import datetime as _dt
        review = Review(
            rating=rating,
            text=text or "Instant delivery, key activated smoothly!",
            create_datetime=_dt.datetime.now(_dt.timezone.utc),
            batstore_order_id=int(order_id) if order_id else None,
        )
        session.add(review)
        await session_commit(session)
        await NotificationService.send_to_admins(
            f"⭐ <b>New Review via Mini App</b>\n\n• Rating: {'⭐' * rating} ({rating}/5)\n• From: tg:{tg_id}\n• Order: #{order_id or 'N/A'}\n• Comment: {text or 'No comment'}",
            None
        )

    return {"status": "success"}


@app.get("/app", response_class=HTMLResponse)
async def tma_storefront():
    """Interactive mobile-first Telegram Mini App (TMA) storefront."""
    from services.storefront_app import get_storefront_html
    response = HTMLResponse(content=get_storefront_html(reload=True))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.post(config.WEBHOOK_PATH)
async def webhook(request: Request):
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_token != config.WEBHOOK_SECRET_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        update_data = await request.json()
        await dp.feed_webhook_update(bot, update_data)
    except Exception as e:
        logging.error("Webhook processing error: %s", e)
    return {"status": "ok"}


_mirror_bots: dict = {}

def _get_mirror_bot(token: str):
    if token not in _mirror_bots:
        from aiogram import Bot as _AiogramBot
        _mirror_bots[token] = _AiogramBot(token=token, session=session)
    return _mirror_bots[token]


@app.post("/webhook/bot/{bot_token}")
async def mirror_bot_webhook(bot_token: str, request: Request):
    """Route updates for secondary/mirror clone bots through the primary Aiogram dispatcher."""
    from services.multibot import MultibotService
    if not await MultibotService.has_token(bot_token):
        raise HTTPException(status_code=403, detail="Unregistered bot token")

    try:
        mirror_bot = _get_mirror_bot(bot_token)
        update_data = await request.json()
        await dp.feed_webhook_update(mirror_bot, update_data)
    except Exception as e:
        logging.error("Mirror bot webhook error for token %s: %s", bot_token[:8], e)
    return {"status": "ok"}


@app.post("/api/referral/withdraw")
async def request_referral_withdrawal(request: Request):
    """Customer requests affiliate commission payout to USDT BEP-20 or ShamCash."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    from services.telegram_auth import extract_and_verify_telegram_user
    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    amount = float(body.get("amount_usd") or 0.0)
    method = str(body.get("method") or "usdt_bep20").strip().lower()
    address = str(body.get("destination_address") or "").strip()

    if amount < 20.0:
        return JSONResponse({"error": "minimum_withdrawal_is_20_usd"}, status_code=400)
    if method not in ("usdt_bep20", "shamcash"):
        return JSONResponse({"error": "invalid_withdrawal_method"}, status_code=400)
    if not address or len(address) < 6:
        return JSONResponse({"error": "invalid_destination_address"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        debited = await UserRepository.try_debit_balance(user.telegram_id, amount, session)
        if not debited:
            available = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
            return JSONResponse({
                "error": "insufficient_balance",
                "needed": amount,
                "available": available
            }, status_code=400)

        from models.referral_withdrawal import ReferralWithdrawalDTO
        from repositories.referral_withdrawal import ReferralWithdrawalRepository
        withdrawal = await ReferralWithdrawalRepository.create(ReferralWithdrawalDTO(
            telegram_id=user.telegram_id,
            amount_usd=amount,
            method=method,
            destination_address=address,
            status="pending"
        ), session)
        await session_commit(session)

        # Notify admins
        await NotificationService.send_to_admins(
            f"💸 <b>طلب سحب أرباح إحالة جديد #{withdrawal.id}</b>\n\n"
            f"• <b>العميل:</b> tg:{user.telegram_id} (@{user.telegram_username or 'none'})\n"
            f"• <b>المبلغ:</b> ${amount:.2f} USD\n"
            f"• <b>الوسيلة:</b> {method.upper()}\n"
            f"• <b>العنوان / الحساب:</b> <code>{address}</code>\n"
            f"• <b>الحالة:</b> قيد المراجعة والاعتماد",
            None
        )

        return {
            "status": "success",
            "withdrawal_id": withdrawal.id,
            "amount_usd": amount,
            "method": method,
            "new_balance": round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
        }


@app.post("/api/admin/referral/withdraw/action")
async def admin_process_referral_withdrawal(request: Request):
    """Admin approves or rejects an affiliate commission withdrawal request."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_id = body.get("admin_tg_id") or body.get("tg_id")
    if not _verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    withdrawal_id = int(body.get("withdrawal_id") or 0)
    action = str(body.get("action") or "").strip().lower()  # 'approve' | 'reject'
    notes = str(body.get("notes") or "").strip()

    if not withdrawal_id or action not in ("approve", "reject"):
        return JSONResponse({"error": "invalid_parameters"}, status_code=400)

    async with get_db_session() as session:
        from repositories.referral_withdrawal import ReferralWithdrawalRepository
        withdrawal = await ReferralWithdrawalRepository.get_by_id(withdrawal_id, session)
        if not withdrawal:
            return JSONResponse({"error": "withdrawal_not_found"}, status_code=404)
        if withdrawal.status != "pending":
            return JSONResponse({"error": "already_processed"}, status_code=400)

        user = await UserRepository.get_by_tgid(withdrawal.telegram_id, session)

        if action == "approve":
            await ReferralWithdrawalRepository.update_status(withdrawal_id, "approved", notes or "Approved by admin", session)
            await session_commit(session)
            if user:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"✅ <b>تم اعتماد وتحويل سحب الأرباح #{withdrawal.id}!</b>\n\n"
                            f"💰 <b>المبلغ:</b> ${withdrawal.amount_usd:.2f} USD\n"
                            f"🌐 <b>الوسيلة:</b> {withdrawal.method.upper()}\n"
                            f"📍 <b>العنوان:</b> <code>{withdrawal.destination_address}</code>\n\n"
                            f"تم إرسال الحوالة بنجاح. شكراً لتعاونك المثمر مع GH Store! 🤝"
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            return {"status": "ok", "action": "approved", "withdrawal_id": withdrawal_id}

        elif action == "reject":
            if user:
                user.top_up_amount = (user.top_up_amount or 0.0) + withdrawal.amount_usd
                await UserRepository.update(user, session)
            await ReferralWithdrawalRepository.update_status(withdrawal_id, "rejected", notes or "Rejected by admin", session)
            await session_commit(session)
            if user:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"❌ <b>تم رفض طلب سحب الأرباح #{withdrawal.id}</b>\n\n"
                            f"💰 تمت إعادة <b>${withdrawal.amount_usd:.2f} USD</b> إلى رصيدك في المتجر.\n"
                            f"📝 <b>السبب:</b> {notes or 'يرجى التواصل مع الدعم للتفاصيل.'}"
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            return {"status": "ok", "action": "rejected", "withdrawal_id": withdrawal_id}

@app.post("/samwebhook")
async def sam_webhook(request: Request):
    """SAM (sam-api.pro) payment webhook.

    Events: invoice.paid | invoice.expired. On payment we credit the customer's
    bot balance (usd_amount) and notify them. SAM requires a 2xx answer always.
    """
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


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    traceback_str = traceback.format_exc()
    admin_notification = (
        f"Critical error caused by {exc}\n\n"
        f"Stack trace:\n{traceback_str}"
    )
    if len(admin_notification) > 4096:
        byte_array = bytearray(admin_notification, 'utf-8')
        admin_notification = BufferedInputFile(byte_array, "exception.txt")
    exc_name = type(exc).__name__
    await NotificationService.send_error_to_admins(f"fastapi_err_{exc_name}", admin_notification, None)
    return JSONResponse(
        status_code=500,
        content={"message": f"An error occurred: {str(exc)}"},
    )


def main() -> None:
    uvicorn.run(
        app,
        host=config.WEBAPP_HOST,
        port=config.WEBAPP_PORT,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )

