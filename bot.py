import asyncio
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
from aiogram import Dispatcher
from fastapi import FastAPI, Request, status, HTTPException

from admin import authentication_backend
from db import create_db_and_tables, engine, get_db_session, session_commit
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
        with open("static/no_image.jpeg", "w") as f:
            f.write(bot_photo_id)
        await MediaService.update_inaccessible_media(bot)
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
        cats = await BatStoreProductRepository.get_categories(session)
        products = await BatStoreProductRepository.get_visible(session)
        sym = config.CURRENCY.get_localized_symbol()
        data = []
        for p in products:
            data.append({
                "id": p.product_id,
                "name": p.name,
                "category": p.category or "Other",
                "price": p.sell_price_usd,
                "sym": sym,
                "description": p.description or "",
                "emoji": p.emoji or "⚡",
                "custom_emoji_id": p.custom_emoji_id,
                "stock": p.stock,
                "delivery_type": p.delivery_type or "stock",
            })
    return {"categories": cats, "products": data}


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
            })

        referrals_count = await UserRepository.get_referrals_qty_by_referrer_id(user.id, session)
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
            "orders": orders_data,
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

