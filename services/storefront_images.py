"""DB-driven storefront image resolution.

All image URLs served to clients come from the database
(storefront_categories.image_url, products.image_url,
promotional_banners.image_url, app_config STORE_* keys) which admins
edit via SQLAdmin or the TMA Admin Center.

This module contains no remote hardcoded URLs. Fallbacks are
same-origin local assets under /static/img/ only.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

LOCAL_CATEGORY_PLACEHOLDER = "/static/img/cat-other.svg"
LOCAL_PRODUCT_PLACEHOLDER = "/static/img/product-placeholder.svg"
LOCAL_HERO = "/static/img/hero.svg"
LOCAL_SHAMCASH_LOGO = "/static/img/pay-shamcash.png"
LOCAL_SYRIATEL_LOGO = "/static/img/pay-syriatel.png"
LOCAL_STORE_LOGO = "/static/img/gh-store-logo-mark.png"

# Single source of default per-category artwork (local assets).
# Used for fresh seeds, data migrations, and runtime fallback when a
# DB row has an empty image_url. Custom DB artwork takes precedence.
DEFAULT_CATEGORY_IMAGES = {
    "Games": "/static/img/cat-games-v2.webp",
    "AI & Chatbots": "/static/img/cat-ai-v2.webp",
    "Streaming & Entertainment": "/static/img/cat-streaming-v2.webp",
    "VPN & Security": "/static/img/cat-vpn-v2.webp",
    "Design & Creative": "/static/img/cat-design-v2.webp",
    "Productivity": "/static/img/cat-productivity-v2.webp",
    "Office & Productivity": "/static/img/cat-office-v2.webp",
    "Accounts & Email": "/static/img/cat-accounts-v2.webp",
    "Education": "/static/img/cat-education-v2.webp",
    "Communication": "/static/img/cat-comms-v2.webp",
    "Social Media": "/static/img/cat-social-v2.webp",
    "Software Keys": "/static/img/cat-keys-v2.webp",
    "Other": "/static/img/cat-other-v2.webp",
}

# Upgrade only exact bundled legacy paths; custom uploads and remote URLs stay intact.
_LEGACY_CATEGORY_IMAGES = {
    url.replace("-v2.webp", ".svg"): url
    for url in DEFAULT_CATEGORY_IMAGES.values()
}

# app_config key -> (response field, local fallback when unset)
IMAGE_SETTINGS = {
    "STORE_LOGO_URL": ("logo", LOCAL_STORE_LOGO),
    "STORE_HERO_IMAGE_URL": ("hero", LOCAL_HERO),
    "STORE_EMPTY_PRODUCT_IMAGE_URL": ("product_placeholder", LOCAL_PRODUCT_PLACEHOLDER),
    "STORE_DEFAULT_CATEGORY_IMAGE_URL": ("category_placeholder", LOCAL_CATEGORY_PLACEHOLDER),
    "PAY_SHAMCASH_LOGO_URL": ("shamcash", LOCAL_SHAMCASH_LOGO),
    "PAY_SYRIATEL_LOGO_URL": ("syriatel", LOCAL_SYRIATEL_LOGO),
}


def _clean(url: str | None) -> str:
    return (url or "").strip()


async def get_store_images(session: AsyncSession | Session) -> dict:
    """Return all global image URLs from DB config with local fallbacks."""
    from services.config import ConfigService
    import os

    out: dict[str, str] = {}
    for key, (field, local_default) in IMAGE_SETTINGS.items():
        try:
            val = await ConfigService.get(session, key, env_fallback=os.environ.get(key, ""))
        except Exception:
            val = ""
        out[field] = _clean(val) or local_default
    return out


def resolve_category_image(category_name: str | None, image_url: str | None, store_images: dict | None = None) -> str:
    """Resolve custom DB art, upgrading bundled legacy covers, then fall back locally."""
    if _clean(image_url):
        url = _clean(image_url)
        return _LEGACY_CATEGORY_IMAGES.get(url, url)
    if category_name and category_name in DEFAULT_CATEGORY_IMAGES:
        return DEFAULT_CATEGORY_IMAGES[category_name]
    if store_images and _clean(store_images.get("category_placeholder")):
        return _clean(store_images.get("category_placeholder"))
    return LOCAL_CATEGORY_PLACEHOLDER


def resolve_product_image(
    product_image_url: str | None,
    category_name: str | None = None,
    category_image_url: str | None = None,
    store_images: dict | None = None,
) -> str:
    """Resolve a product thumbnail: product -> category -> global placeholder."""
    if _clean(product_image_url):
        return _clean(product_image_url)
    if _clean(category_image_url):
        return resolve_category_image(category_name, category_image_url, store_images)
    if category_name and category_name in DEFAULT_CATEGORY_IMAGES:
        return DEFAULT_CATEGORY_IMAGES[category_name]
    if store_images and _clean(store_images.get("product_placeholder")):
        return _clean(store_images.get("product_placeholder"))
    return LOCAL_PRODUCT_PLACEHOLDER
