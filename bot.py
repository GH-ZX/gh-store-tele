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
from models.promotional_banner import PromotionalBannerAdmin
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
        try:
            await bot.set_my_description(
                description=(
                    "🛍️ Welcome to GH Store — your premier destination for digital subscriptions, "
                    "AI tools (ChatGPT, Claude, Gemini), streaming accounts, and license keys.\n\n"
                    "⚡ Instant delivery · 🔒 Guaranteed warranty · 💳 Pay with Stars, Crypto, or Syrian Cash."
                )
            )
            await bot.set_my_short_description(
                short_description="🛍️ Premier Digital Subscriptions, AI Tools & Instant Licenses Store."
            )
        except Exception as e:
            logging.warning("Could not set bot descriptions: %s", e)
    except Exception as e:
        logging.warning("Could not set bot commands: %s", e)
    from services.order_polling import poll_pending_orders, periodic_catalog_sync, periodic_balance_monitor
    _polling_task = asyncio.create_task(poll_pending_orders())
    _sync_loop_task = asyncio.create_task(periodic_catalog_sync())
    _balance_monitor_task = asyncio.create_task(periodic_balance_monitor())
    from services.financial_digest import daily_digest_cron
    _digest_task = asyncio.create_task(daily_digest_cron())
    CartRecoveryService.set_redis(redis)
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
admin.add_model_view(PromotionalBannerAdmin)
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


from routes import (
    catalog_router,
    checkout_router,
    wallet_router,
    admin_router,
    webhooks_router,
)
from routes.tma_catalog import get_tma_catalog, broadcast_sse_event
from routes.common import verify_admin as _verify_admin

app.include_router(catalog_router)
app.include_router(checkout_router)
app.include_router(wallet_router)
app.include_router(admin_router)
app.include_router(webhooks_router)

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

