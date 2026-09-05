import asyncio
import datetime
import os
import logging
import sys
import traceback
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


async def _sync_batstore_catalog() -> None:
    """Sync the BatStore catalog from the reseller API on startup (best-effort)."""
    try:
        async with get_db_session() as session:
            created, updated = await BatStoreService.sync_catalog(session)
        logging.info("BatStore catalog sync complete: %s created, %s updated", created, updated)
    except Exception as e:  # noqa: BLE001
        logging.error("BatStore catalog sync failed (continuing): %s", e)


_polling_task: asyncio.Task | None = None
_sync_loop_task: asyncio.Task | None = None
_balance_monitor_task: asyncio.Task | None = None
_digest_task: asyncio.Task | None = None
_recovery_task: asyncio.Task | None = None
_rates_task: asyncio.Task | None = None


_recovery_task: asyncio.Task | None = None
async def _startup() -> None:
    global _polling_task
    await create_db_and_tables()
    async with get_db_session() as session:
        await ConfigService.seed_defaults(session)
        await ConfigService.seed_from_env(session)
    if config.BATSTORE_SYNC_ENABLED:
        asyncio.create_task(_sync_batstore_catalog())
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
    static = Path("static")
    from services.currency_rates import currency_rates_cron, CurrencyRateService
    _rates_task = asyncio.create_task(currency_rates_cron())
    asyncio.create_task(CurrencyRateService.update_rates())
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
admin.add_model_view(AdminAuditLogAdmin)
admin.add_model_view(GiftVoucherAdmin)
admin.add_model_view(StorefrontCategoryAdmin)
app.include_router(processing_router)
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
            })
        store_logo_url = await ConfigService.get(session, "STORE_LOGO_URL", env_fallback=os.environ.get("STORE_LOGO_URL", ""))
    return {"categories": cats_list, "products": data, "store_logo_url": store_logo_url or ""}


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


@app.get("/api/user-data")
async def get_tma_user_data(tg_id: int):
    """Return user profile, balance, VIP rank, referral data, and orders for TMA."""
    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return {"error": "user_not_found"}

        from services.user import get_vip_tier_info, format_currency_display
        tier_label, discount_pct = get_vip_tier_info(user.consume_records)
        balance = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
        curr_pref = getattr(user, "currency_preference", "USD") or "USD"

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
        me = await bot.get_me()
        # Fetch real Telegram profile photo
        photo_url = None
        try:
            photos = await bot.get_user_profile_photos(user.telegram_id, limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id
                file_obj = await bot.get_file(file_id)
                photo_url = f"https://api.telegram.org/file/bot{config.TOKEN}/{file_obj.file_path}"
        except Exception as e:
            logging.debug("Could not fetch profile photo: %s", e)
        is_admin = bool(user.telegram_id in config.ADMIN_ID_LIST)
        admin_stats = None
        if is_admin:
            try:
                from models.batstore_order import BatStoreOrder
                from models.user import User
                stmt_rev = select(func.coalesce(func.sum(BatStoreOrder.total_sell), 0.0)).where(BatStoreOrder.status == "completed")
                tot_rev = (await session_execute(stmt_rev, session)).scalar_one()
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

                admin_stats = {
                    "total_revenue": round(float(tot_rev), 2),
                    "total_orders_count": int(tot_ord),
                    "total_users_count": int(tot_usr),
                    "total_users_balance": round(float(tot_bal), 2),
                    "syp_usd_rate": syp_market,
                    "referral_commission_percent": ref_val,
                    "global_margin_percent": float(margin_cfg or 20.0),
                    "stars_to_usd_rate": float(stars_cfg or 0.01),
                    "store_announcement": announcement_cfg or "",
                    "autorefund_enabled": (await ConfigService.get(session, "AUTOREFUND_ENABLED", default="false")).lower() in ("true", "1", "yes"),
                }
            except Exception as e:
                logging.error("Failed to compile admin stats: %s", e)

        return {
            "telegram_id": user.telegram_id,
            "username": user.telegram_username or "",
            "photo_url": photo_url,
            "balance": balance,
            "display_balance": format_currency_display(balance, curr_pref),
            "currency_preference": curr_pref,
            "language": user.language.value if hasattr(user.language, "value") else str(user.language),
            "vip_tier": tier_label,
            "vip_discount": discount_pct,
            "total_spent": round(user.consume_records or 0.0, 2),
            "referral_code": user.referral_code or "",
            "bot_username": me.username or "GHStoreBot",
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

    tg_id = int(body.get("tg_id") or 0)
    product_id = int(body.get("product_id") or 0)
    quantity = max(1, min(10, int(body.get("quantity") or 1)))

    if not tg_id or not product_id:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        product = await BatStoreProductRepository.get_by_product_id(product_id, session)
        if not product or product.hidden:
            return JSONResponse({"error": "product_not_found"}, status_code=404)

        total = round(quantity * product.sell_price_usd, 2)
        tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0))
        if discount_pct > 0:
            disc_val = round(total * (discount_pct / 100.0), 2)
            total = max(0.01, round(total - disc_val, 2))
        vol_disc_pct = BatStoreService.get_volume_discount(quantity)
        if vol_disc_pct > 0:
            vol_disc = round(total * (vol_disc_pct / 100.0), 2)
            total = max(0.01, round(total - vol_disc, 2))
        coupon_code = (body.get("coupon_code") or "").strip()
        if coupon_code:
            from repositories.coupon import CouponRepository
            from enums.coupon_type import CouponType
            coupon = await CouponRepository.get_by_code(coupon_code, session)
            if coupon and coupon.is_active:
                if not (coupon.usage_limit and coupon.usage_count >= coupon.usage_limit):
                    if coupon.type == CouponType.PERCENT:
                        c_disc = total * (float(coupon.value) / 100.0)
                    else:
                        c_disc = float(coupon.value)
                    total = max(0.01, round(total - c_disc, 2))
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
            placed = await BatStoreService.place_order(
                session, product.product_id, quantity,
                customer_reference=customer_ref,
                idempotency_key=customer_ref,
            )
            ext_ref = placed.get("order", {}).get("id") or placed.get("order_id")
            order_obj = placed.get("order", {}) or {}
            items = order_obj.get("items") or []
            goods_list = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
        except Exception as e:
            logging.error("BatStore in-app checkout failed: %s", e)
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

        cart_products = []
        raw_total = 0.0
        for it in items_input:
            pid = int(it.get("product_id") or 0)
            qty = max(1, min(20, int(it.get("quantity") or 1)))
            prod = await BatStoreProductRepository.get_by_product_id(pid, session)
            if not prod or prod.hidden:
                return JSONResponse({"error": f"Product #{pid} is unavailable"}, status_code=400)
            line_total = round(qty * prod.sell_price_usd, 2)
            raw_total += line_total
            cart_products.append({"product": prod, "quantity": qty, "line_total": line_total})

        tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0), getattr(user, "custom_discount_pct", None))
        total = raw_total
        if discount_pct > 0:
            disc_val = round(total * (discount_pct / 100.0), 2)
            total = max(0.01, round(total - disc_val, 2))

        coupon_code = (body.get("coupon_code") or "").strip()
        if coupon_code:
            from repositories.coupon import CouponRepository
            from enums.coupon_type import CouponType
            coupon = await CouponRepository.get_by_code(coupon_code, session)
            if coupon and coupon.is_active:
                if not (coupon.usage_limit and coupon.usage_count >= coupon.usage_limit):
                    if coupon.type == CouponType.PERCENT:
                        c_disc = total * (float(coupon.value) / 100.0)
                    else:
                        c_disc = float(coupon.value)
                    total = max(0.01, round(total - c_disc, 2))
                    await CouponRepository.increment_usage(coupon.id, session)

        total = round(total, 2)

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
        tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0))

        total_usd = round(qty * product.sell_price_usd, 2)
        if discount_pct > 0:
            disc = round(total_usd * (discount_pct / 100.0), 2)
            total_usd = max(0.01, round(total_usd - disc, 2))

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

        elif method == "crypto":
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
                return {"status": "ok", "type": "url", "url": payment.paymentUrl or payment.address, "invoice_id": getattr(payment, "id", "") or inv_uuid, "amount": amount, "currency": "USD"}
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

        discount = 0.0
        if coupon.type == CouponType.PERCENT:
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



def _verify_admin(tg_id: int | None) -> bool:
    if not tg_id:
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

        refund_amount = round(float(order.total_sell or 0.0), 2)
        user = await UserRepository.get_by_tgid(order.telegram_id, session)
        if user:
            user.top_up_amount = (user.top_up_amount or 0.0) + refund_amount
            await UserRepository.update(user, session)
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

    return {"status": "ok", "refunded_amount": refund_amount, "order_id": order_id}


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
            margin = max(0.0, float(o.total_sell or 0.0) - cost)
            orders_out.append({
                "id": o.id,
                "telegram_id": o.telegram_id,
                "username": f"@{uname}" if uname else "",
                "status": o.status,
                "total_sell": round(float(o.total_sell or 0.0), 2),
                "cost_usd": round(cost, 2),
                "margin": round(margin, 2),
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
    from services.storefront_app import STOREFRONT_HTML
    return HTMLResponse(content=STOREFRONT_HTML)


@app.post(config.WEBHOOK_PATH)
async def webhook(request: Request):
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_token != config.WEBHOOK_SECRET_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        update_data = await request.json()
        await dp.feed_webhook_update(bot, update_data)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
        return {"status": "error"}, status.HTTP_500_INTERNAL_SERVER_ERROR


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
                    except Exception as e:  # noqa: BLE001
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
        except Exception as e:  # noqa: BLE001
            logging.error("SAM webhook processing error: %s", e, exc_info=True)

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

