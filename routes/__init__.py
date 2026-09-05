"""FastAPI route modules for GH Store Telegram Bot and Mini App."""
from routes.tma_catalog import router as catalog_router
from routes.tma_checkout import router as checkout_router
from routes.tma_wallet import router as wallet_router
from routes.tma_admin import router as admin_router
from routes.webhooks import router as webhooks_router

__all__ = [
    "catalog_router",
    "checkout_router",
    "wallet_router",
    "admin_router",
    "webhooks_router",
]
