"""G2Bulk Wholesale API Client & Game Fulfillment Engine.

Documentation: https://api.g2bulk.com/docs
Base URL: https://api.g2bulk.com/v1
Authentication: Header X-API-Key: <key>
Telegram Bot for Keys & Wallet: @G2BULKBOT

Specialized exclusively for:
- Category: "Games"
- Subfolder 1: "Instant recharge Games" (direct player ID / server ID top-up)
- Subfolder 2: "Vouchers" (game digital PINs / codes with redemption manuals)
"""
import asyncio
import logging
import os
import re
import uuid
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

import config
from db import session_commit, session_execute
from models.batstore_product import (
    BatStoreProduct,
    MarginType,
)
from models.storefront_category import StorefrontCategory
from models.storefront_folder import StorefrontFolder
from repositories.batstore_product import BatStoreProductRepository
from services.config import ConfigService
from services.sale_pricing import compute_reseller_price


class G2BulkAPIError(Exception):
    """Raised when G2Bulk API returns an error."""


class G2BulkOutOfStockError(G2BulkAPIError):
    """Raised when G2Bulk product or denomination is out of stock."""


class _PersistentClientContext:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False


# Knowledge base of redemption instructions for popular game vouchers
VOUCHER_REDEMPTION_GUIDES: dict[str, dict[str, Any]] = {
    "pubg": {
        "url": "https://www.midasbuy.com",
        "name_ar": "ببجي موبايل (PUBG Mobile)",
        "name_en": "PUBG Mobile UC",
        "steps_en": [
            "Visit www.midasbuy.com and select PUBG Mobile.",
            "Log in and enter your Player ID to verify your character nickname.",
            "Enter the voucher PIN code received from GH Store.",
            "Click OK to redeem. Your UC will be credited to your game account immediately."
        ],
        "steps_ar": [
            "توجه إلى موقع midasbuy.com الرسمي واختر لعبة ببجي موبايل.",
            "سجل الدخول وأدخل معرف اللاعب (Player ID) وتأكد من ظهور اسم حسابك.",
            "أدخل كود القسيمة (PIN) المستلم من متجر GH Store.",
            "اضغط تأكيد، وسيتم شحن الشدات (UC) في حسابك داخل اللعبة فوراً."
        ]
    },
    "free_fire": {
        "url": "https://shop2game.com",
        "name_ar": "فري فاير (Free Fire)",
        "name_en": "Free Fire Diamonds",
        "steps_en": [
            "Visit shop2game.com and select Free Fire.",
            "Log in using your Player ID.",
            "Choose Garena Voucher as payment method and enter your voucher PIN.",
            "Confirm redemption to receive your diamonds in-game instantly."
        ],
        "steps_ar": [
            "توجه إلى موقع shop2game.com واختر فري فاير.",
            "سجل الدخول بواسطة معرف اللاعب (Player ID) الخاص بك.",
            "اختر طريقة الدفع عبر بطاقة قارينا وأدخل كود القسيمة المستلم.",
            "اضغط تأكيد لإضافة الجواهر فوراً إلى حسابك في اللعبة."
        ]
    },
    "razer": {
        "url": "https://gold.razer.com",
        "name_ar": "ريدزر جولد (Razer Gold)",
        "name_en": "Razer Gold PIN",
        "steps_en": [
            "Log in to your Razer Gold account at gold.razer.com.",
            "Click 'Reload Now' and select 'Razer Gold PIN'.",
            "Enter the PIN code received and follow instructions to add funds.",
            "Use your balance to purchase gaming credits across thousands of games."
        ],
        "steps_ar": [
            "سجل الدخول إلى حسابك في موقع gold.razer.com.",
            "اضغط على زر 'Reload Now' (إعادة الشحن) واختر 'Razer Gold PIN'.",
            "أدخل رمز PIN المستلم واضغط متابعة لإضافة الرصيد إلى محفظتك.",
            "استخدم رصيد المحفظة للشحن في آلاف الألعاب والتطبيقات المدعومة."
        ]
    },
    "steam": {
        "url": "https://store.steampowered.com/account/redeemwalletcode",
        "name_ar": "ستيم (Steam)",
        "name_en": "Steam Wallet Code",
        "steps_en": [
            "Launch the Steam client or go to store.steampowered.com/account/redeemwalletcode.",
            "Sign in to your Steam account.",
            "Enter the Steam Wallet Code into the input field.",
            "Click Continue. The funds will be added to your Steam Wallet immediately."
        ],
        "steps_ar": [
            "افتح تطبيق Steam أو توجه إلى store.steampowered.com/account/redeemwalletcode.",
            "سجل الدخول إلى حساب ستيم الخاص بك.",
            "أدخل كود محفظة ستيم في خانة الرمز.",
            "اضغط متابعة (Continue) لإضافة الرصيد إلى محفظتك واستخدامه لشراء الألعاب."
        ]
    },
    "playstation": {
        "url": "https://store.playstation.com",
        "name_ar": "بلايستيشن (PlayStation)",
        "name_en": "PlayStation Network (PSN)",
        "steps_en": [
            "Open PlayStation Store on your console or visit store.playstation.com.",
            "Sign in to your PlayStation Network account.",
            "Click on your profile avatar at the top and select 'Redeem Code'.",
            "Enter the 12-digit voucher code and select Redeem."
        ],
        "steps_ar": [
            "افتح متجر PlayStation Store من جهاز الكونسول أو المتصفح.",
            "سجل الدخول إلى حساب شبكة PlayStation Network الخاص بك.",
            "اضغط على صورة ملفك الشخصي بالأعلى واختر 'Redeem Code' (استرداد الرمز).",
            "أدخل رمز القسيمة المكون من 12 خانة واضغط Redeem لتعبئة المحفظة."
        ]
    },
    "xbox": {
        "url": "https://redeem.microsoft.com",
        "name_ar": "إكس بوكس (Xbox)",
        "name_en": "Xbox Gift Card / Game Pass",
        "steps_en": [
            "Go to redeem.microsoft.com in any web browser.",
            "Sign in with your Microsoft / Xbox account.",
            "Enter the 25-character code received.",
            "Click Next and confirm to apply the gift card or subscription."
        ],
        "steps_ar": [
            "توجه إلى موقع redeem.microsoft.com عبر المتصفح.",
            "سجل الدخول بحساب Microsoft / Xbox الخاص بك.",
            "أدخل الكود المكون من 25 رمزاً في الخانة المخصصة.",
            "اضغط التالي (Next) وتأكيد لتفعيل الرصيد أو الاشتراك في حسابك."
        ]
    },
    "roblox": {
        "url": "https://www.roblox.com/redeem",
        "name_ar": "روبلوكس (Roblox)",
        "name_en": "Roblox Gift Card",
        "steps_en": [
            "Go to roblox.com/redeem in your web browser.",
            "Log in to the Roblox account where you want the credit.",
            "Enter the PIN code from your GH Store order.",
            "Click Redeem to add Robux or Credit to your account."
        ],
        "steps_ar": [
            "توجه إلى موقع roblox.com/redeem عبر المتصفح.",
            "سجل الدخول إلى حساب روبلوكس المراد شحنه.",
            "أدخل كود PIN المستلم من طلبك في متجر GH Store.",
            "اضغط Redeem لإضافة رصيد Robux أو رصيد المحفظة إلى حسابك فوراً."
        ]
    },
    "valorant": {
        "url": "https://playvalorant.com",
        "name_ar": "فالورانت (Valorant)",
        "name_en": "Valorant Points (VP)",
        "steps_en": [
            "Launch the Valorant game client and log in.",
            "Click the VP icon in the top-right corner next to the Store tab.",
            "Select 'Prepaid Cards & Codes' payment method.",
            "Enter the voucher code and click Submit to receive your VP."
        ],
        "steps_ar": [
            "افتح لعبة فالورانت وسجل الدخول إلى حسابك.",
            "اضغط على أيقونة نقاط VP في الزاوية العلوية بجوار تبويب المتجر.",
            "اختر طريقة الدفع 'Prepaid Cards & Codes' (البطاقات مسبقة الدفع).",
            "أدخل كود القسيمة واضغط Submit لاستلام النقاط فوراً داخل اللعبة."
        ]
    }
}

GENERIC_VOUCHER_GUIDE = {
    "url": "",
    "name_ar": "قسيمة ألعاب رقمية",
    "name_en": "Digital Game Voucher",
    "steps_en": [
        "Visit the official game redemption website or open the game store.",
        "Sign in with your game account.",
        "Navigate to 'Redeem Code' or 'Prepaid Voucher' section.",
        "Enter the digital voucher code and confirm to activate."
    ],
    "steps_ar": [
        "توجه إلى الموقع الرسمي لاسترداد رموز اللعبة أو افتح متجر اللعبة.",
        "سجل الدخول إلى حساب اللعبة الخاص بك.",
        "انتقل إلى قسم 'استرداد الرمز' (Redeem Code) أو البطاقات مسبقة الدفع.",
        "أدخل الكود الرقمي المستلم واضغط تأكيد لتفعيل المحتوى فوراً."
    ]
}


class G2BulkService:
    BASE_DEFAULT = "https://api.g2bulk.com/v1"
    _shared_client: httpx.AsyncClient | None = None

    @classmethod
    async def _client(cls):
        if cls._shared_client is None or cls._shared_client.is_closed:
            cls._shared_client = httpx.AsyncClient(timeout=35.0)
        return _PersistentClientContext(cls._shared_client)

    @classmethod
    async def close_client(cls) -> None:
        """Close persistent HTTP client session."""
        if cls._shared_client and not cls._shared_client.is_closed:
            await cls._shared_client.aclose()
            cls._shared_client = None

    @staticmethod
    async def resolve_api_key(session: AsyncSession | Session | None = None) -> str:
        """Resolve G2Bulk API key from database config, falling back to environment."""
        if session is not None:
            try:
                db_key = await ConfigService.get(session, "G2BULK_API_KEY")
                if db_key and str(db_key).strip():
                    return str(db_key).strip()
            except Exception:
                pass
        env_key = os.environ.get("G2BULK_API_KEY", "").strip()
        if env_key:
            return env_key
        return getattr(config, "G2BULK_API_KEY", "").strip()

    @staticmethod
    async def resolve_api_url(session: AsyncSession | Session | None = None) -> str:
        """Resolve G2Bulk base URL from config or environment."""
        if session is not None:
            try:
                db_url = await ConfigService.get(session, "G2BULK_API_URL")
                if db_url and str(db_url).strip():
                    return str(db_url).strip().rstrip("/")
            except Exception:
                pass
        env_url = os.environ.get("G2BULK_API_URL", "").strip()
        if env_url:
            return env_url.rstrip("/")
        return getattr(config, "G2BULK_API_URL", G2BulkService.BASE_DEFAULT).strip().rstrip("/")

    @staticmethod
    async def _headers(session: AsyncSession | Session | None = None, auth_required: bool = True) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "GHStore/1.0 (+https://gh-store.me)",
        }
        if auth_required:
            key = await G2BulkService.resolve_api_key(session)
            if not key:
                raise G2BulkAPIError("G2BULK_API_KEY is not configured in settings or environment.")
            headers["X-API-Key"] = key
        return headers

    # ------------------------------------------------------------- Wallet & Profile

    @staticmethod
    async def get_balance(session: AsyncSession | Session | None = None) -> dict[str, Any]:
        """Fetch current G2Bulk wallet balance and user profile (/v1/getMe)."""
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=True)
        async with await G2BulkService._client() as client:
            try:
                resp = await client.get(f"{base_url}/getMe", headers=headers)
            except Exception as e:
                raise G2BulkAPIError(f"G2Bulk /getMe connection error: {e}") from e

        if resp.status_code != 200:
            raise G2BulkAPIError(f"G2Bulk /getMe returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if not data.get("success", False) and "balance" not in data:
            raise G2BulkAPIError(f"G2Bulk /getMe failed: {data}")
        return {
            "balance": float(data.get("balance") or 0.0),
            "username": str(data.get("username") or ""),
            "user_id": data.get("user_id"),
            "first_name": str(data.get("first_name") or ""),
        }

    @staticmethod
    async def get_cached_balance(session: AsyncSession | Session, redis_client=None, force_refresh: bool = False) -> float:
        """Fetch G2Bulk balance with 30s Redis TTL caching."""
        cache_key = "ghstore:cache:g2bulk_balance"
        r = redis_client or BatStoreProductRepository._redis
        if not force_refresh and r is not None:
            try:
                cached = await r.get(cache_key)
                if cached is not None:
                    return float(cached)
            except Exception:
                pass

        try:
            info = await G2BulkService.get_balance(session)
            bal = float(info.get("balance", 0.0))
            if r is not None:
                try:
                    await r.setex(cache_key, 30, str(bal))
                except Exception:
                    pass
            return bal
        except Exception as e:
            logging.debug("G2Bulk get_cached_balance error: %s", e)
            return 0.0 if force_refresh else 9999.0

    # ------------------------------------------------------------- Games / Instant Recharge

    @staticmethod
    async def get_games(session: AsyncSession | Session | None = None) -> list[dict[str, Any]]:
        """Fetch all supported direct top-up games from G2Bulk (/v1/games)."""
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=False)
        async with await G2BulkService._client() as client:
            try:
                resp = await client.get(f"{base_url}/games", headers=headers)
            except Exception as e:
                raise G2BulkAPIError(f"G2Bulk /games connection error: {e}") from e

        if resp.status_code != 200:
            raise G2BulkAPIError(f"G2Bulk /games returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return data.get("games") or []

    @staticmethod
    async def get_game_catalogue(game_code: str, session: AsyncSession | Session | None = None) -> list[dict[str, Any]]:
        """Fetch all items / denominations for a specific game (/v1/games/:code/catalogue)."""
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=False)
        clean_code = str(game_code).strip()
        async with await G2BulkService._client() as client:
            try:
                resp = await client.get(f"{base_url}/games/{clean_code}/catalogue", headers=headers)
            except Exception as e:
                raise G2BulkAPIError(f"G2Bulk /games/{clean_code}/catalogue connection error: {e}") from e

        if resp.status_code != 200:
            raise G2BulkAPIError(f"G2Bulk /games/{clean_code}/catalogue returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return data.get("catalogues") or []

    @staticmethod
    async def get_game_fields(game_code: str, session: AsyncSession | Session | None = None) -> dict[str, Any]:
        """Fetch player input fields schema for a game (POST /v1/games/fields)."""
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=False)
        clean_code = str(game_code).strip()
        async with await G2BulkService._client() as client:
            try:
                resp = await client.post(f"{base_url}/games/fields", headers=headers, json={"game": clean_code})
            except Exception as e:
                logging.debug("G2Bulk /games/fields error for %s: %s", clean_code, e)
                return {"fields": ["userid"], "notes": ""}

        if resp.status_code == 200:
            data = resp.json()
            info = data.get("info") or {}
            return {
                "fields": info.get("fields") or ["userid"],
                "notes": info.get("notes") or "",
            }
        # Fallback for games without separate fields definition
        return {"fields": ["userid"], "notes": ""}

    @staticmethod
    async def get_game_servers(game_code: str, session: AsyncSession | Session | None = None) -> dict[str, str]:
        """Fetch server options map for a game (POST /v1/games/servers).

        Returns dict of {label: value} or empty dict if game does not require servers (403).
        """
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=False)
        clean_code = str(game_code).strip()
        async with await G2BulkService._client() as client:
            try:
                resp = await client.post(f"{base_url}/games/servers", headers=headers, json={"game": clean_code})
            except Exception as e:
                logging.debug("G2Bulk /games/servers error for %s: %s", clean_code, e)
                return {}

        if resp.status_code == 200:
            data = resp.json()
            servers = data.get("servers") or {}
            if isinstance(servers, dict):
                return servers
            if isinstance(servers, list):
                return {s: s for s in servers}
        return {}

    @staticmethod
    async def check_player_id(
        game_code: str,
        user_id: str,
        server_id: str | None = None,
        charname: str | None = None,
        session: AsyncSession | Session | None = None
    ) -> dict[str, Any]:
        """Validate player account existence and retrieve in-game nickname (POST /v1/games/checkPlayerId)."""
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=False)
        payload: dict[str, Any] = {
            "game": str(game_code).strip(),
            "user_id": str(user_id).strip(),
        }
        if server_id:
            payload["server_id"] = str(server_id).strip()
        if charname:
            payload["charname"] = str(charname).strip()

        async with await G2BulkService._client() as client:
            try:
                resp = await client.post(f"{base_url}/games/checkPlayerId", headers=headers, json=payload)
            except Exception as e:
                raise G2BulkAPIError(f"Player verification connection error: {e}") from e

        data = resp.json() if resp.text else {}
        is_valid = (data.get("valid") == "valid" or resp.status_code == 200 and data.get("name"))
        return {
            "valid": bool(is_valid),
            "name": str(data.get("name") or ""),
            "openid": str(data.get("openid") or ""),
            "message": data.get("message") or ("Player verified successfully" if is_valid else "Invalid player ID"),
            "raw": data,
        }

    @staticmethod
    async def create_game_order(
        session: AsyncSession | Session,
        game_code: str,
        catalogue_name: str,
        player_id: str,
        server_id: str | None = None,
        charname: str | None = None,
        remark: str | None = None,
        callback_url: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Place an instant game top-up order (POST /v1/games/:code/order)."""
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=True)
        if idempotency_key:
            # G2Bulk requires 36-char UUID format for idempotency key
            if len(idempotency_key) == 36:
                headers["X-Idempotency-Key"] = idempotency_key
            else:
                headers["X-Idempotency-Key"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, idempotency_key))

        payload: dict[str, Any] = {
            "catalogue_name": str(catalogue_name).strip(),
            "player_id": str(player_id).strip(),
        }
        if server_id:
            payload["server_id"] = str(server_id).strip()
        if charname:
            payload["charname"] = str(charname).strip()
        if remark:
            payload["remark"] = str(remark).strip()
        if callback_url:
            payload["callback_url"] = str(callback_url).strip()

        clean_code = str(game_code).strip()
        async with await G2BulkService._client() as client:
            try:
                resp = await client.post(f"{base_url}/games/{clean_code}/order", headers=headers, json=payload)
            except Exception as e:
                raise G2BulkAPIError(f"G2Bulk /games/{clean_code}/order connection error: {e}") from e

        if resp.status_code not in (200, 201):
            err_msg = resp.text[:250]
            if "stock" in err_msg.lower() or resp.status_code == 409:
                raise G2BulkOutOfStockError(f"Game recharge denomination out of stock: {err_msg}")
            raise G2BulkAPIError(f"G2Bulk /games/{clean_code}/order returned {resp.status_code}: {err_msg}")

        data = resp.json()
        order_info = data.get("order") or {}
        return {
            "success": bool(data.get("success", True)),
            "order_id": order_info.get("order_id") or data.get("order_id"),
            "status": order_info.get("status") or "PENDING",
            "game": order_info.get("game") or clean_code,
            "catalogue": order_info.get("catalogue") or catalogue_name,
            "player_name": order_info.get("player_name") or "",
            "raw": data,
        }

    @staticmethod
    async def get_game_order_status(order_id: int | str, session: AsyncSession | Session | None = None) -> dict[str, Any]:
        """Check status of a game top-up order (POST /v1/games/order/status)."""
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=True)
        async with await G2BulkService._client() as client:
            try:
                resp = await client.post(f"{base_url}/games/order/status", headers=headers, json={"order_id": int(order_id)})
            except Exception as e:
                raise G2BulkAPIError(f"G2Bulk /games/order/status error: {e}") from e

        if resp.status_code != 200:
            raise G2BulkAPIError(f"G2Bulk /games/order/status returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return data

    # ------------------------------------------------------------- Vouchers / Digital Goods

    @staticmethod
    async def get_voucher_categories(session: AsyncSession | Session | None = None) -> list[dict[str, Any]]:
        """Fetch all voucher categories (/v1/category)."""
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=False)
        async with await G2BulkService._client() as client:
            try:
                resp = await client.get(f"{base_url}/category", headers=headers)
            except Exception as e:
                raise G2BulkAPIError(f"G2Bulk /category connection error: {e}") from e

        if resp.status_code != 200:
            raise G2BulkAPIError(f"G2Bulk /category returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return data.get("categories") or []

    @staticmethod
    async def get_voucher_products(session: AsyncSession | Session | None = None) -> list[dict[str, Any]]:
        """Fetch all voucher products (/v1/products)."""
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=False)
        async with await G2BulkService._client() as client:
            try:
                resp = await client.get(f"{base_url}/products", headers=headers)
            except Exception as e:
                raise G2BulkAPIError(f"G2Bulk /products connection error: {e}") from e

        if resp.status_code != 200:
            raise G2BulkAPIError(f"G2Bulk /products returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return data.get("products") or []

    @staticmethod
    async def get_voucher_product(product_id: int, session: AsyncSession | Session | None = None) -> dict[str, Any]:
        """Fetch single voucher product by ID with fresh unit price and stock (/v1/products/:id)."""
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=False)
        async with await G2BulkService._client() as client:
            try:
                resp = await client.get(f"{base_url}/products/{int(product_id)}", headers=headers)
            except Exception as e:
                raise G2BulkAPIError(f"G2Bulk /products/{product_id} connection error: {e}") from e

        if resp.status_code != 200:
            raise G2BulkAPIError(f"G2Bulk /products/{product_id} returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return data.get("product") or data
    @staticmethod
    async def purchase_voucher(
        session: AsyncSession | Session,
        product_id: int,
        quantity: int = 1,
        idempotency_key: str | None = None,
        max_poll_attempts: int = 4,
    ) -> dict[str, Any]:
        """Purchase voucher from G2Bulk (POST /v1/products/:id/purchase).

        If response is PENDING, polls /v1/orders/:id/delivery until COMPLETED.
        """
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=True)
        if idempotency_key:
            if len(idempotency_key) == 36:
                headers["X-Idempotency-Key"] = idempotency_key
            else:
                headers["X-Idempotency-Key"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, idempotency_key))

        payload = {"quantity": max(1, int(quantity))}
        async with await G2BulkService._client() as client:
            try:
                resp = await client.post(
                    f"{base_url}/products/{int(product_id)}/purchase",
                    headers=headers,
                    json=payload
                )
            except Exception as e:
                raise G2BulkAPIError(f"G2Bulk voucher purchase connection error: {e}") from e

        if resp.status_code not in (200, 201):
            err_msg = resp.text[:250]
            if "stock" in err_msg.lower() or resp.status_code == 409:
                raise G2BulkOutOfStockError(f"Voucher out of stock: {err_msg}")
            raise G2BulkAPIError(f"G2Bulk purchase returned {resp.status_code}: {err_msg}")

        data = resp.json()
        status_val = str(data.get("status") or "").upper()
        order_id = data.get("order_id")
        delivery_items = data.get("delivery_items") or []

        # If pending and order_id available, short poll delivery endpoint
        if status_val == "PENDING" and order_id and not delivery_items:
            for _ in range(max_poll_attempts):
                await asyncio.sleep(2.0)
                try:
                    deliv_res = await G2BulkService.get_delivery(order_id, session)
                    if deliv_res.get("status") == "COMPLETED" and deliv_res.get("delivery_items"):
                        delivery_items = deliv_res["delivery_items"]
                        status_val = "COMPLETED"
                        break
                    elif deliv_res.get("status") in ("REFUNDED", "FAILED"):
                        raise G2BulkAPIError("Upstream voucher order failed and was refunded.")
                except Exception as ex_deliv:
                    logging.debug("Polling voucher delivery attempt failed: %s", ex_deliv)

        return {
            "success": bool(data.get("success", True)),
            "order_id": order_id,
            "status": status_val or ("COMPLETED" if delivery_items else "PENDING"),
            "delivery_items": delivery_items,
            "product_title": data.get("product_title") or "",
            "raw": data,
        }

    @staticmethod
    async def get_delivery(order_id: int | str, session: AsyncSession | Session | None = None) -> dict[str, Any]:
        """Poll voucher delivery endpoint (/v1/orders/:id/delivery)."""
        base_url = await G2BulkService.resolve_api_url(session)
        headers = await G2BulkService._headers(session, auth_required=True)
        async with await G2BulkService._client() as client:
            try:
                resp = await client.get(f"{base_url}/orders/{int(order_id)}/delivery", headers=headers)
            except Exception as e:
                raise G2BulkAPIError(f"G2Bulk /orders/{order_id}/delivery error: {e}") from e

        if resp.status_code == 200:
            d = resp.json()
            return {
                "status": "COMPLETED",
                "delivery_items": d.get("delivery_items") or [],
                "order_id": d.get("order_id") or order_id,
            }
        elif resp.status_code == 202:
            return {"status": "PROCESSING", "delivery_items": []}
        elif resp.status_code == 410:
            return {"status": "REFUNDED", "delivery_items": []}
        raise G2BulkAPIError(f"Delivery polling returned {resp.status_code}: {resp.text[:150]}")

    @staticmethod
    def extract_delivery_goods(order_resp: dict[str, Any]) -> list[str]:
        """Extract delivery keys or voucher codes into clean list of strings."""
        goods: list[str] = []
        raw_items = order_resp.get("delivery_items")
        if isinstance(raw_items, list):
            for item in raw_items:
                if isinstance(item, str):
                    goods.append(item.strip())
                elif isinstance(item, dict):
                    c = item.get("code") or item.get("pin") or item.get("key")
                    if c:
                        goods.append(str(c).strip())
        elif isinstance(raw_items, str) and raw_items.strip():
            goods.append(raw_items.strip())
        return goods

    # ------------------------------------------------------------- Helpers & Matching

    @staticmethod
    def is_game_voucher_category(title: str) -> bool:
        """Filter vouchers so only gaming gift cards & voucher codes are imported."""
        t_low = title.lower()
        game_keywords = [
            "pubg", "free fire", "razer", "steam", "playstation", "psn",
            "xbox", "roblox", "valorant", "nintendo", "minecraft", "jawaker",
            "yalla ludo", "honor of kings", "new state", "netease", "riot",
            "ea fc", "fifa", "cod", "call of duty", "garena", "league of legends"
        ]
        non_game_keywords = ["airbnb", "doordash", "netflix", "noon", "amazon", "itunes", "apple itunes", "google play", "telegram redeem"]
        if any(ng in t_low for ng in non_game_keywords):
            return False
        return any(kw in t_low for kw in game_keywords)

    @staticmethod
    def get_redemption_guide_for_title(title: str) -> dict[str, Any]:
        """Retrieve redemption instructions for a voucher brand."""
        t_low = title.lower()
        for key, guide in VOUCHER_REDEMPTION_GUIDES.items():
            if key in t_low:
                return guide
        return GENERIC_VOUCHER_GUIDE

    # ------------------------------------------------------------- Catalog Synchronization

    @staticmethod
    async def ensure_categories_and_folders(session: AsyncSession | Session) -> tuple[StorefrontCategory, StorefrontFolder, StorefrontFolder]:
        """Ensure 'Games' category and subfolders 'Instant recharge Games' & 'Vouchers' exist in database."""
        # 1. Category "Games"
        stmt_cat = select(StorefrontCategory).where(StorefrontCategory.name == "Games")
        cat = (await session_execute(stmt_cat, session)).scalar_one_or_none()
        if not cat:
            cat = StorefrontCategory(
                name="Games",
                name_ar="الألعاب",
                name_en="Games",
                image_url="/static/img/cat-games.svg",
                icon="🎮",
                preview_ar="شحن فوري مباشر للألعاب، وقسائم وبطاقات الهدايا الرقمية",
                preview_en="Instant direct game top-ups, game vouchers & digital gift cards",
                sort_order=2,
                hidden=False,
            )
            session.add(cat)
            await session_commit(session)
            await session.refresh(cat)

        # 2. Folder 1: Instant recharge Games
        stmt_f1 = select(StorefrontFolder).where(StorefrontFolder.key == "instant_recharge_games")
        f1 = (await session_execute(stmt_f1, session)).scalar_one_or_none()
        if not f1:
            f1 = StorefrontFolder(
                key="instant_recharge_games",
                category="Games",
                title_en="Instant recharge Games",
                title_ar="شحن ألعاب فوري",
                icon="⚡",
                sort_order=10,
                hidden=False,
                matching_keywords="instant,recharge,topup,top-up,direct",
            )
            session.add(f1)

        # 3. Folder 2: Vouchers
        stmt_f2 = select(StorefrontFolder).where(StorefrontFolder.key == "vouchers")
        f2 = (await session_execute(stmt_f2, session)).scalar_one_or_none()
        if not f2:
            f2 = StorefrontFolder(
                key="vouchers",
                category="Games",
                title_en="Vouchers",
                title_ar="قسائم الألعاب",
                icon="🎟️",
                sort_order=20,
                hidden=False,
                matching_keywords="voucher,pin,card,giftcard,code",
            )
            session.add(f2)

        await session_commit(session)
        return cat, f1, f2

    @staticmethod
    async def sync_catalog(session: AsyncSession | Session) -> tuple[int, int]:
        """Synchronize both Instant Recharge Games and Game Vouchers from G2Bulk into GH Store."""
        logging.info("Starting G2Bulk Games & Vouchers catalog synchronization...")
        created_count = 0
        updated_count = 0

        # Step 1: Ensure category and folders exist
        await G2BulkService.ensure_categories_and_folders(session)

        # Step 2: Global reseller margin settings
        global_margin_pct = float(await ConfigService.get(session, "MARGIN_PERCENT", default="12.0") or 12.0)
        global_margin_fixed = float(await ConfigService.get(session, "MARGIN_FIXED", default="0.15") or 0.15)
        global_reseller_margin = float(await ConfigService.get(session, "GLOBAL_RESELLER_MARGIN_PERCENT", default="8.0") or 8.0)

        # Step 3: Fetch G2Bulk Games list
        try:
            games_list = await G2BulkService.get_games(session)
        except Exception as e:
            logging.warning("G2Bulk get_games failed during sync: %s", e)
            games_list = []

        # Prioritized games and popular titles
        featured_priority = {
            "pubg_mobile": 1, "freefire_id": 2, "freefire_eu": 3, "mlbb": 4, "codm_sgmy": 5,
            "deltaforce": 6, "aoem": 7, "bullet_echo": 8, "genshin_impact": 9, "brawl_stars": 10,
            "clash_of_clans": 11, "honor_of_kings": 12, "roblox": 13, "coa": 14, "dmc": 15,
            "afkjourney": 16, "pixel_gun_3d": 17, "fifa_futcoins_console": 18
        }
        # Sort games: featured first, then others
        games_list.sort(key=lambda x: featured_priority.get(x.get("code", ""), 999))

        # Sync every supported game; the product page holds each game's full
        # denomination catalogue in extra_meta.
        target_games = games_list
        sem = asyncio.Semaphore(8)

        async def fetch_game_meta(g_info):
            code = g_info.get("code")
            async with sem:
                catalogue_error = False
                try:
                    cat_items = await G2BulkService.get_game_catalogue(code, session)
                except Exception:
                    catalogue_error = True
                    cat_items = []
                try:
                    f_info = await G2BulkService.get_game_fields(code, session)
                except Exception:
                    f_info = {"fields": ["userid"], "notes": ""}
                try:
                    s_map = await G2BulkService.get_game_servers(code, session)
                except Exception:
                    s_map = {}
                return g_info, cat_items, f_info, s_map, catalogue_error

        results = await asyncio.gather(*(fetch_game_meta(g) for g in target_games), return_exceptions=True)

        for res in results:
            if isinstance(res, Exception) or not res:
                continue
            g, catalogue_items, fields_info, servers_map, catalogue_error = res
            g_id = g.get("id")
            g_code = g.get("code")
            g_name = g.get("name")
            if not g_id or not g_code:
                continue

            product_id = 30000000 + int(g_id)
            stmt = select(BatStoreProduct).where(BatStoreProduct.product_id == product_id)
            existing = (await session_execute(stmt, session)).scalar_one_or_none()
            if catalogue_error:
                logging.warning("Skipping %s: catalogue request failed; preserving current product state.", g_code)
                continue
            if not catalogue_items:
                if existing and existing.supplier == "g2bulk":
                    existing.hidden = True
                    existing.hidden_reason = "catalogue"
                    updated_count += 1
                continue
            if existing and existing.margin_type == MarginType.FIXED_PRICE:
                continue

            min_cost = 0.80
            if catalogue_items:
                min_cost = min(float(item.get("amount") or 0.80) for item in catalogue_items)

            processed_items = []
            for item in catalogue_items:
                cost_i = float(item.get("amount") or 0.0)
                sell_i = round((cost_i * (1.0 + global_margin_pct / 100.0)) + global_margin_fixed, 2)
                resell_i = compute_reseller_price(cost=cost_i, retail_price=sell_i, global_reseller_margin_pct=global_reseller_margin)
                processed_items.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "cost": cost_i,
                    "price": sell_i,
                    "reseller_price": resell_i,
                })

            base_sell = round((min_cost * (1.0 + global_margin_pct / 100.0)) + global_margin_fixed, 2)
            base_resell = compute_reseller_price(cost=min_cost, retail_price=base_sell, global_reseller_margin_pct=global_reseller_margin)

            extra_meta = {
                "type": "instant_recharge",
                "game_code": g_code,
                "game_id": g_id,
                "required_fields": fields_info.get("fields", ["userid"]),
                "notes": fields_info.get("notes", ""),
                "servers": servers_map,
                "items": processed_items,
            }

            img_url = g.get("image_url") or ""
            if img_url and not img_url.startswith("http"):
                img_url = f"https://api.g2bulk.com{img_url}"

            desc_en = f"Official instant top-up for {g_name}. Credits are delivered straight into your game account."
            desc_ar = f"شحن فوري ومباشر لحساب لعبة {g_name}. يتم إرسال الرصيد تلقائياً إلى حسابك داخل اللعبة."
            if existing:
                existing.name = f"{g_name} (Instant Recharge)"
                existing.cost_usd = min_cost
                existing.sell_price_usd = base_sell
                existing.reseller_price_usd = base_resell
                existing.image_url = img_url or existing.image_url
                existing.extra_meta = extra_meta
                existing.stock = 9999
                existing.delivery_type = "direct_topup"
                existing.supplier = "g2bulk"
                if existing.hidden_reason != "admin":
                    existing.hidden = False
                    existing.hidden_reason = None
                existing.server_badge = "سيرفر 3 (G2Bulk Games)"
                updated_count += 1
            else:
                new_prod = BatStoreProduct(
                    product_id=product_id,
                    name=f"{g_name} (Instant Recharge)",
                    custom_name=g_name,
                    custom_name_ar=g_name,
                    custom_group="Instant recharge Games",
                    custom_group_ar="شحن ألعاب فوري",
                    description=desc_en,
                    description_ar=desc_ar,
                    emoji="⚡",
                    image_url=img_url,
                    cost_usd=min_cost,
                    sell_price_usd=base_sell,
                    reseller_price_usd=base_resell,
                    category="Games",
                    delivery_type="direct_topup",
                    stock=9999,
                    warranty_days=7,
                    hidden=False,
                    reseller_key_override=g_code,
                    supplier="g2bulk",
                    server_badge="سيرفر 3 (G2Bulk Games)",
                    extra_meta=extra_meta,
                )
                session.add(new_prod)
                created_count += 1

        # Step 4: Fetch G2Bulk Game Vouchers
        try:
            voucher_cats = await G2BulkService.get_voucher_categories(session)
            all_voucher_prods = await G2BulkService.get_voucher_products(session)
        except Exception as e:
            logging.warning("G2Bulk get_voucher_products failed during sync: %s", e)
            voucher_cats = []
            all_voucher_prods = []

        # Filter categories for gaming only
        game_cat_ids = {c["id"]: c for c in voucher_cats if G2BulkService.is_game_voucher_category(c.get("title", ""))}

        # Group voucher products by gaming category/brand
        vouchers_by_cat: dict[int, list[dict]] = {}
        for vp in all_voucher_prods:
            c_id = vp.get("category_id")
            if c_id in game_cat_ids:
                vouchers_by_cat.setdefault(c_id, []).append(vp)

        for cat_id, v_items in vouchers_by_cat.items():
            cat_info = game_cat_ids[cat_id]
            cat_title = cat_info.get("title", "Game Vouchers")
            guide = G2BulkService.get_redemption_guide_for_title(cat_title)

            # Product ID for grouped brand voucher: 35,000,000 + cat_id
            brand_prod_id = 35000000 + int(cat_id)

            stmt_v = select(BatStoreProduct).where(BatStoreProduct.product_id == brand_prod_id)
            existing_v = (await session_execute(stmt_v, session)).scalar_one_or_none()

            # Prepare items array with pricing
            items_arr = []
            for item in v_items:
                c_cost = float(item.get("unit_price") or 0.0)
                c_sell = round((c_cost * (1.0 + global_margin_pct / 100.0)) + global_margin_fixed, 2)
                c_resell = compute_reseller_price(cost=c_cost, retail_price=c_sell, global_reseller_margin_pct=global_reseller_margin)
                items_arr.append({
                    "id": item.get("id"),
                    "name": item.get("title"),
                    "cost": c_cost,
                    "price": c_sell,
                    "reseller_price": c_resell,
                    "face_value": item.get("face_value"),
                    "stock": item.get("stock", 0),
                })

            min_v_cost = min((float(i.get("unit_price") or 0.0) for i in v_items), default=1.0)
            base_v_sell = round((min_v_cost * (1.0 + global_margin_pct / 100.0)) + global_margin_fixed, 2)
            base_v_resell = compute_reseller_price(cost=min_v_cost, retail_price=base_v_sell, global_reseller_margin_pct=global_reseller_margin)

            extra_meta_v = {
                "type": "voucher",
                "category_id": cat_id,
                "redemption_url": guide.get("url", ""),
                "instructions_en": guide.get("steps_en", []),
                "instructions_ar": guide.get("steps_ar", []),
                "items": items_arr,
            }

            v_img = cat_info.get("image_url") or ""
            if v_img and not v_img.startswith("http"):
                v_img = f"https://api.g2bulk.com{v_img}"

            desc_v_en = f"Official digital voucher codes for {cat_title}. Code delivered immediately upon purchase with clear redemption guide."
            desc_v_ar = f"قسائم وأكواد شحن رقمية معتمدة لـ {cat_title}. استلام فوري للكود مباشرة بعد الشراء مع خطوات الاستخدام الكاملة."

            if existing_v:
                existing_v.name = f"{cat_title} (Digital Vouchers)"
                existing_v.cost_usd = min_v_cost
                existing_v.sell_price_usd = base_v_sell
                existing_v.reseller_price_usd = base_v_resell
                existing_v.extra_meta = extra_meta_v
                existing_v.image_url = v_img or existing_v.image_url
                existing_v.supplier = "g2bulk"
                existing_v.delivery_type = "voucher"
                if existing_v.hidden_reason != "admin":
                    existing_v.hidden = False
                    existing_v.hidden_reason = None
                existing_v.server_badge = "سيرفر 3 (G2Bulk Vouchers)"
                updated_count += 1
            else:
                new_v = BatStoreProduct(
                    product_id=brand_prod_id,
                    name=f"{cat_title} (Digital Vouchers)",
                    custom_name=cat_title,
                    custom_name_ar=guide.get("name_ar") or cat_title,
                    custom_group="Vouchers",
                    custom_group_ar="قسائم الألعاب",
                    description=desc_v_en,
                    description_ar=desc_v_ar,
                    emoji="🎟️",
                    image_url=v_img,
                    cost_usd=min_v_cost,
                    sell_price_usd=base_v_sell,
                    reseller_price_usd=base_v_resell,
                    category="Games",
                    delivery_type="voucher",
                    stock=9999,
                    warranty_days=30,
                    hidden=False,
                    reseller_key_override=str(cat_id),
                    supplier="g2bulk",
                    server_badge="سيرفر 3 (G2Bulk Vouchers)",
                    extra_meta=extra_meta_v,
                )
                session.add(new_v)
                created_count += 1

        await session_commit(session)
        await BatStoreProductRepository.invalidate_cache()
        logging.info("G2Bulk catalog sync completed: %d created, %d updated.", created_count, updated_count)
        return created_count, updated_count
