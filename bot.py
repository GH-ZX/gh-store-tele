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
from fastapi.responses import JSONResponse, HTMLResponse
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
from services.cart_recovery import CartRecoveryService, cart_recovery_cron
from repositories.sam_payment import SamPaymentRepository
from repositories.user import UserRepository
from repositories.button_media import ButtonMediaRepository
from repositories.batstore_product import BatStoreProductRepository
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
async def _startup() -> None:
    global _polling_task
    await create_db_and_tables()
    async with get_db_session() as session:
        await ConfigService.seed_defaults(session)
        await ConfigService.seed_from_env(session)
    if config.BATSTORE_SYNC_ENABLED:
        asyncio.create_task(_sync_batstore_catalog())
    asyncio.create_task(_set_webhook_with_retry())
    from services.order_polling import poll_pending_orders, periodic_catalog_sync, periodic_balance_monitor
    _polling_task = asyncio.create_task(poll_pending_orders())
    _sync_loop_task = asyncio.create_task(periodic_catalog_sync())
    _balance_monitor_task = asyncio.create_task(periodic_balance_monitor())
    from services.financial_digest import daily_digest_cron
    _digest_task = asyncio.create_task(daily_digest_cron())
    _recovery_task = asyncio.create_task(cart_recovery_cron())
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
    global _polling_task, _sync_loop_task, _balance_monitor_task, _digest_task, _recovery_task
    logging.warning('Shutting down..')
    for t in (_polling_task, _sync_loop_task, _balance_monitor_task, _digest_task, _recovery_task):
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


@app.get("/app", response_class=HTMLResponse)
async def tma_storefront():
    """Interactive mobile-first Telegram Mini App (TMA) storefront."""
    sym = config.CURRENCY.get_localized_symbol()
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>GH Store</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root {{
      --bg: var(--tg-theme-bg-color, #0f172a);
      --text: var(--tg-theme-text-color, #f8fafc);
      --hint: var(--tg-theme-hint-color, #94a3b8);
      --btn: var(--tg-theme-button-color, #38bdf8);
      --btn-text: var(--tg-theme-button-text-color, #ffffff);
      --card: var(--tg-theme-secondary-bg-color, #1e293b);
      --border: rgba(255, 255, 255, 0.08);
    }}
    * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 12px; }}
    header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }}
    h1 {{ font-size: 20px; margin: 0; font-weight: 700; display: flex; align-items: center; gap: 6px; }}
    .search-box {{ width: 100%; margin-bottom: 12px; }}
    .search-box input {{ width: 100%; background: var(--card); border: 1px solid var(--border); border-radius: 10px; color: var(--text); padding: 10px 14px; font-size: 14px; outline: none; }}
    .chips {{ display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px; margin-bottom: 12px; }}
    .chip {{ background: var(--card); border: 1px solid var(--border); border-radius: 20px; padding: 6px 14px; font-size: 13px; white-space: nowrap; cursor: pointer; }}
    .chip.active {{ background: var(--btn); color: var(--btn-text); border-color: var(--btn); }}
    .grid {{ display: grid; grid-template-columns: 1fr; gap: 10px; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 14px; display: flex; flex-direction: column; justify-content: space-between; }}
    .card-title {{ font-size: 15px; font-weight: 600; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }}
    .card-desc {{ font-size: 13px; color: var(--hint); margin-bottom: 10px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
    .card-footer {{ display: flex; align-items: center; justify-content: space-between; }}
    .price {{ font-size: 16px; font-weight: 700; color: #38bdf8; }}
    .buy-btn {{ background: var(--btn); color: var(--btn-text); border: none; border-radius: 8px; padding: 8px 14px; font-size: 13px; font-weight: 600; cursor: pointer; }}
    .stock-badge {{ font-size: 11px; color: var(--hint); margin-top: 2px; }}
  </style>
</head>
<body>
  <header>
    <h1>🛍️ GH Store</h1>
    <div id="user-badge" style="font-size: 13px; color: var(--hint);">Storefront</div>
  </header>
  <div class="search-box">
    <input type="text" id="search" placeholder="🔍 Search products (Claude, Gemini, Netflix...)" oninput="filterProducts()">
  </div>
  <div class="chips" id="categories"></div>
  <div class="grid" id="products"></div>
  <script>
    const tg = window.Telegram?.WebApp;
    if (tg) {{ tg.ready(); tg.expand(); }}
    let allProducts = [];
    let activeCategory = "All";

    async function loadCatalog() {{
      try {{
        const res = await fetch('/api/catalog');
        const data = await res.json();
        allProducts = data.products || [];
        renderCategories(["All", ...(data.categories || [])]);
        renderProducts(allProducts);
      }} catch (e) {{
        document.getElementById('products').innerHTML = '<div style="color: var(--hint); text-align: center; padding: 20px;">Could not load catalog.</div>';
      }}
    }}

    function renderCategories(cats) {{
      const container = document.getElementById('categories');
      container.innerHTML = cats.map(c => `
        <div class="chip ${{c === activeCategory ? 'active' : ''}}" onclick="selectCategory('${{c}}')">${{c}}</div>
      `).join('');
    }}

    function selectCategory(cat) {{
      activeCategory = cat;
      document.querySelectorAll('.chip').forEach(el => el.classList.toggle('active', el.innerText === cat));
      filterProducts();
    }}

    function filterProducts() {{
      const q = (document.getElementById('search').value || '').toLowerCase();
      const filtered = allProducts.filter(p => {{
        const matchesCat = activeCategory === "All" || p.category === activeCategory;
        const matchesSearch = !q || p.name.toLowerCase().includes(q) || (p.description || '').toLowerCase().includes(q);
        return matchesCat && matchesSearch;
      }});
      renderProducts(filtered);
    }}

    function renderProducts(list) {{
      const container = document.getElementById('products');
      if (!list.length) {{
        container.innerHTML = '<div style="color: var(--hint); text-align: center; padding: 30px;">No products found.</div>';
        return;
      }}
      container.innerHTML = list.map(p => `
        <div class="card">
          <div>
            <div class="card-title">${{p.emoji || '⚡'}} ${{p.name}}</div>
            <div class="card-desc">${{p.description || 'Instant digital activation & delivery.'}}</div>
          </div>
          <div class="card-footer">
            <div>
              <div class="price">${{p.price ? p.price.toFixed(2) + p.sym : 'N/A'}}</div>
              <div class="stock-badge">${{p.stock ? p.stock + ' in stock' : 'Instant order'}}</div>
            </div>
            <button class="buy-btn" onclick="buyProduct(${{p.id}}, '${{encodeURIComponent(p.name)}}')">Buy Now</button>
          </div>
        </div>
      `).join('');
    }}

    function buyProduct(id, name) {{
      if (tg) {{
        tg.sendData(JSON.stringify({{ action: "buy_batstore", product_id: id }}));
        tg.close();
      }} else {{
        alert("Please open this store from inside Telegram!");
      }}
    }}
    loadCatalog();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)


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

