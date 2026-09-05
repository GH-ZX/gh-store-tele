"""ProdSeller API Client and Multi-Supplier Fulfillment Service.

Documentation: https://prodseller.com/api-docs/
Base URL: https://prodseller.com/v1
Authentication: Header X-API-Key: psk_...
"""
import hashlib
import logging
import os
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_commit
import config
from models.batstore_product import (
    BatStoreProduct,
    BatStoreProductDTO,
    MarginType,
    auto_categorize,
)
from repositories.batstore_product import BatStoreProductRepository
from services.config import ConfigService
from services.custom_emoji import CustomEmojiService
from utils.telegram import clean_tg_emojis


class ProdSellerAPIError(Exception):
    """Raised when ProdSeller API returns an error."""


class ProdSellerOutOfStockError(ProdSellerAPIError):
    """Raised when ProdSeller product is out of stock."""


class _PersistentClientContext:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False


class ProdSellerService:
    BASE_URL = "https://prodseller.com/v1"
    _shared_client: httpx.AsyncClient | None = None

    @classmethod
    async def _client(cls):
        if cls._shared_client is None or cls._shared_client.is_closed:
            cls._shared_client = httpx.AsyncClient(timeout=30.0)
        return _PersistentClientContext(cls._shared_client)

    @staticmethod
    async def resolve_api_key(session: AsyncSession | Session | None = None) -> str:
        """Resolve ProdSeller API key from database config, falling back to environment."""
        if session is not None:
            try:
                db_key = await ConfigService.get(session, "PRODSELLER_API_KEY")
                if db_key and str(db_key).strip():
                    return str(db_key).strip()
            except Exception:
                pass
        env_key = os.environ.get("PRODSELLER_API_KEY", "").strip()
        if env_key:
            return env_key
        return getattr(config, "PRODSELLER_API_KEY", "").strip()

    @staticmethod
    async def _headers(session: AsyncSession | Session | None = None) -> dict[str, str]:
        key = await ProdSellerService.resolve_api_key(session)
        if not key:
            raise ProdSellerAPIError("PRODSELLER_API_KEY is not configured in settings or environment.")
        return {
            "X-API-Key": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    async def get_balance(session: AsyncSession | Session | None = None) -> dict[str, Any]:
        """Fetch current ProdSeller wallet balance and membership tier."""
        headers = await ProdSellerService._headers(session)
        async with await ProdSellerService._client() as client:
            try:
                resp = await client.get(f"{ProdSellerService.BASE_URL}/balance", headers=headers)
            except Exception as e:
                raise ProdSellerAPIError(f"ProdSeller /balance connection error: {e}") from e

        if resp.status_code != 200:
            raise ProdSellerAPIError(f"ProdSeller /balance returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return {
            "balance": float(data.get("balance") or 0.0),
            "membership": str(data.get("membership") or "standard"),
            "username": str(data.get("username") or ""),
            "telegram_id": data.get("telegramId"),
        }

    @staticmethod
    async def get_cached_balance(session: AsyncSession | Session, redis_client=None) -> float:
        """Fetch ProdSeller balance with 30s Redis TTL caching for circuit breaking."""
        cache_key = "ghstore:cache:prodseller_balance"
        r = redis_client or BatStoreProductRepository._redis
        if r is not None:
            try:
                cached = await r.get(cache_key)
                if cached is not None:
                    return float(cached)
            except Exception:
                pass

        try:
            info = await ProdSellerService.get_balance(session)
            bal = float(info.get("balance") or 0.0)
            if r is not None:
                try:
                    await r.setex(cache_key, 30, str(bal))
                except Exception:
                    pass
            return bal
        except Exception as e:
            logging.warning("Failed to fetch ProdSeller balance: %s", e)
            return 9999.0

    get_cached_reseller_balance = get_cached_balance
    @staticmethod
    async def list_products(session: AsyncSession | Session | None = None) -> list[dict[str, Any]]:
        """Fetch all active products from ProdSeller."""
        headers = await ProdSellerService._headers(session)
        async with await ProdSellerService._client() as client:
            try:
                resp = await client.get(f"{ProdSellerService.BASE_URL}/products", headers=headers)
            except Exception as e:
                raise ProdSellerAPIError(f"ProdSeller /products connection error: {e}") from e

        if resp.status_code != 200:
            raise ProdSellerAPIError(f"ProdSeller /products returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return data.get("products") or []

    @staticmethod
    def generate_product_id(mongo_id: str) -> int:
        """Deterministically map a 24-char MongoDB ID to a stable integer product_id in range 2,000,000 - 2,899,999."""
        h = hashlib.md5(mongo_id.encode("utf-8")).hexdigest()
        offset = int(h[:7], 16) % 900000
        return 2000000 + offset

    @staticmethod
    async def place_order(
        session: AsyncSession | Session,
        mongo_product_id: str,
        quantity: int = 1,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Purchase product from ProdSeller balance with idempotency key protection."""
        headers = await ProdSellerService._headers(session)
        if idempotency_key:
            headers["Idempotency-Key"] = str(idempotency_key)[:100]

        payload = {"productId": mongo_product_id, "quantity": quantity}
        async with await ProdSellerService._client() as client:
            try:
                resp = await client.post(
                    f"{ProdSellerService.BASE_URL}/orders",
                    headers=headers,
                    json=payload,
                )
            except Exception as e:
                raise ProdSellerAPIError(f"ProdSeller order connection error: {e}") from e

        if resp.status_code == 409:
            raise ProdSellerOutOfStockError(f"ProdSeller product {mongo_product_id} is out of stock (409 Conflict)")
        if resp.status_code == 402:
            raise ProdSellerAPIError("ProdSeller insufficient balance (402)")
        if resp.status_code not in (200, 201):
            err_text = resp.text[:200]
            if any(w in err_text.lower() for w in ("stock", "rupture", "solde", "epuise")):
                raise ProdSellerOutOfStockError(f"ProdSeller stock error: {err_text}")
            raise ProdSellerAPIError(f"ProdSeller /orders returned {resp.status_code}: {err_text}")

        data = resp.json()
        if "error" in data:
            raise ProdSellerAPIError(f"ProdSeller error: {data['error']}")
        return data

    @staticmethod
    def extract_delivery_goods(order_data: dict[str, Any]) -> list[str]:
        """Extract delivered key(s) from ProdSeller order response."""
        goods: list[str] = []
        if order_data.get("deliveredKey"):
            goods.append(str(order_data["deliveredKey"]))
        for k in (order_data.get("deliveredKeys") or []):
            if str(k) not in goods:
                goods.append(str(k))
        return goods

    @staticmethod
    async def sync_catalog(session: AsyncSession | Session) -> tuple[int, int]:
        """Pull /v1/products from ProdSeller and upsert into batstore_products table.

        Assigns supplier='prodseller' and server_badge='سيرفر 2 (ProdSeller)'.
        Computes selling price using the store's global margin rules.
        """
        from services.batstore import BatStoreService

        key = await ProdSellerService.resolve_api_key(session)
        if not key:
            logging.info("ProdSeller API key not configured; skipping sync.")
            return 0, 0

        global_percent, global_fixed, global_type = await BatStoreService._global_margin(session)
        products = await ProdSellerService.list_products(session)
        rules = await CustomEmojiService.get_rules(session)

        created = 0
        updated = 0
        for p in products:
            mongo_id = str(p.get("id") or "").strip()
            if not mongo_id:
                continue

            int_pid = ProdSellerService.generate_product_id(mongo_id)
            name = str(p.get("name") or f"ProdSeller {mongo_id[:6]}").strip()
            cost = float(p.get("price") or 0.0)
            in_stock = bool(p.get("inStock", True))
            stock_count = 10 if in_stock else 0

            detected_emoji, detected_custom_id = CustomEmojiService.detect_icon(name, rules)
            category = auto_categorize(name)
            sell_price = BatStoreService.compute_sell_price(cost, global_percent, global_fixed, None, None, global_type)

            existing = await BatStoreProductRepository.get_by_product_id(int_pid, session)
            if existing is None:
                dto = BatStoreProductDTO(
                    product_id=int_pid,
                    name=name,
                    description=clean_tg_emojis(p.get("description")),
                    description_ar=clean_tg_emojis(p.get("description")),
                    emoji="",
                    custom_emoji_id=detected_custom_id,
                    image_url=p.get("imageUrl"),
                    cost_usd=cost,
                    standard_price_usd=float(p.get("publicPrice") or cost * 1.2),
                    delivery_type="stock" if in_stock else "activation",
                    stock=stock_count,
                    warranty_days=30,
                    margin_type=None,
                    margin_value=None,
                    category=category,
                    sell_price_usd=sell_price,
                    hidden=False,
                    reseller_key_override=mongo_id,
                    supplier="prodseller",
                    server_badge="سيرفر 2 (ProdSeller)",
                )
                await BatStoreProductRepository.create(dto, session)
                created += 1
            else:
                existing.cost_usd = cost
                existing.stock = stock_count
                existing.reseller_key_override = mongo_id
                existing.supplier = "prodseller"
                existing.server_badge = "سيرفر 2 (ProdSeller)"
                if not in_stock:
                    existing.stock = 0
                await BatStoreProductRepository.update(existing, session)
                updated += 1

        await session_commit(session)
        logging.info("ProdSeller catalog sync complete: %s created, %s updated", created, updated)
        return created, updated
