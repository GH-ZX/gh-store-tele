import asyncio
import logging

try:
    import httpx
except Exception:  # pragma: no cover - httpx is optional at import in tests
    httpx = None  # type: ignore

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from db import session_commit
from models.batstore_product import BatStoreProduct, BatStoreProductDTO, MarginType, auto_categorize, auto_detect_icon, format_product_icon
from repositories.batstore_product import BatStoreProductRepository
from services.config import ConfigService
from services.custom_emoji import CustomEmojiService
from services.restock_notification import RestockNotificationService
from utils.telegram import clean_tg_emojis
API_TEST_PRODUCT_ID = 2147483000


class BatStoreAPIError(Exception):
    """Raised when the BatStore/VenteBot reseller API returns an error."""


class BatStoreOutOfStockError(BatStoreAPIError):
    """Raised when the upstream product is out of stock."""

class _PersistentClientContext:
    def __init__(self, client: "httpx.AsyncClient"):
        self._client = client

    async def __aenter__(self) -> "httpx.AsyncClient":
        return self._client

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False


class BatStoreService:
    BASE_DEFAULT = "https://ventetelegrambotrailway-production.up.railway.app"
    HEADER_KEY = "X-Reseller-Key"
    _shared_client: "httpx.AsyncClient | None" = None

    @classmethod
    async def _client(cls):
        if cls._shared_client is None or cls._shared_client.is_closed:
            cls._shared_client = httpx.AsyncClient(timeout=30.0)
        return _PersistentClientContext(cls._shared_client)

    @classmethod
    async def close_client(cls) -> None:
        if cls._shared_client is not None and not cls._shared_client.is_closed:
            await cls._shared_client.aclose()
            cls._shared_client = None

    @staticmethod
    def _headers(key: str | None) -> dict[str, str]:
        headers = {}
        if key:
            headers[BatStoreService.HEADER_KEY] = str(key)
        return headers

    @staticmethod
    async def _resolve(session: AsyncSession | Session) -> tuple[str, str | None, str | None]:
        """Resolve primary base URL, secondary failover mirror URL, and API key."""
        try:
            base = await ConfigService.get(session, "BATSTORE_API_URL",
                                           env_fallback=config.BATSTORE_API_URL,
                                           default=BatStoreService.BASE_DEFAULT)
            base_sec = await ConfigService.get(session, "BATSTORE_API_URL_SECONDARY",
                                               env_fallback=getattr(config, "BATSTORE_API_URL_SECONDARY", None),
                                               default=None)
            key = await ConfigService.get(session, "BATSTORE_API_KEY",
                                          env_fallback=config.BATSTORE_API_KEY)
        except Exception as e:
            logging.warning("ConfigService resolution failed, using env fallback: %s", e)
            base = ConfigService.fallback_from_env("BATSTORE_API_URL", BatStoreService.BASE_DEFAULT)
            base_sec = ConfigService.fallback_from_env("BATSTORE_API_URL_SECONDARY", None)
            key = ConfigService.fallback_from_env("BATSTORE_API_KEY")
        return (base or BatStoreService.BASE_DEFAULT), base_sec, key

    @staticmethod
    async def _request(method: str, path: str, session: AsyncSession | Session,
                       key_override: str | None = None, **kwargs) -> "httpx.Response":
        base, base_sec, key = await BatStoreService._resolve(session)
        effective_key = key_override or key
        headers = BatStoreService._headers(effective_key)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        async with await BatStoreService._client() as client:
            try:
                resp = await client.request(method, f"{base}{path}", headers=headers, **kwargs)
                if resp.status_code in (502, 503, 504) and base_sec:
                    logging.warning("Primary reseller API %s returned %s; retrying secondary mirror %s", base, resp.status_code, base_sec)
                    resp = await client.request(method, f"{base_sec}{path}", headers=headers, **kwargs)
                return resp
            except Exception as e:
                if base_sec:
                    logging.warning("Primary reseller API %s failed (%s); retrying secondary mirror %s", base, e, base_sec)
                    return await client.request(method, f"{base_sec}{path}", headers=headers, **kwargs)
                raise
    @staticmethod
    async def me(session: AsyncSession | Session) -> dict:
        resp = await BatStoreService._request("GET", "/api/reseller/me", session)
        if resp.status_code != 200:
            raise BatStoreAPIError(f"GET /me {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if not data.get("success"):
            raise BatStoreAPIError(f"GET /me failed: {resp.text[:200]}")
        return data

    @staticmethod
    async def list_products(session: AsyncSession | Session, lang: str | None = None) -> list[dict]:
        params = {"lang": lang} if lang else None
        resp = await BatStoreService._request("GET", "/api/reseller/products", session, params=params)
        if resp.status_code != 200:
            raise BatStoreAPIError(f"GET /products {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if not data.get("success"):
            raise BatStoreAPIError(f"GET /products failed: {resp.text[:200]}")
        return data.get("products", [])

    @staticmethod
    async def quote(session: AsyncSession | Session,
                    product_id: int,
                    quantity: int = 1,
                    key_override: str | None = None) -> dict:
        payload = {"product_id": product_id, "quantity": quantity}
        resp = await BatStoreService._request("POST", "/api/reseller/quote", session,
                                              key_override=key_override, json=payload)
        if resp.status_code != 200:
            raise BatStoreAPIError(f"POST /quote {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if not data.get("success"):
            raise BatStoreAPIError(f"POST /quote failed: {resp.text[:200]}")
        return data

    @staticmethod
    async def place_order(session: AsyncSession | Session,
                          product_id: int,
                          quantity: int = 1,
                          activation_identifier: str | None = None,
                          customer_reference: str | None = None,
                          idempotency_key: str | None = None,
                          key_override: str | None = None) -> dict:
        payload = {"product_id": product_id, "quantity": quantity}
        if activation_identifier:
            payload["activation_identifier"] = activation_identifier
        if customer_reference:
            payload["customer_reference"] = customer_reference
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        resp = await BatStoreService._request("POST", "/api/reseller/orders", session,
                                              key_override=key_override, json=payload)
        if resp.status_code not in (200, 402):
            raw_err = resp.text[:200]
            lower_err = raw_err.lower()
            if any(k in lower_err for k in ("out of stock", "insufficient stock", "no items", "stock unavailable", "not enough stock")):
                raise BatStoreOutOfStockError(f"Product #{product_id} is out of stock upstream: {raw_err}")
            raise BatStoreAPIError(f"POST /orders {resp.status_code}: {raw_err}")
        data = resp.json()
        if not data.get("success"):
            err_msg = str(data.get("message") or data.get("error") or data)[:200]
            lower_msg = err_msg.lower()
            if any(k in lower_msg for k in ("out of stock", "insufficient stock", "no items", "stock unavailable", "not enough stock")):
                raise BatStoreOutOfStockError(f"Product #{product_id} is out of stock upstream: {err_msg}")
            raise BatStoreAPIError(f"POST /orders failed: {err_msg}")
        return data

    @staticmethod
    async def get_cached_reseller_balance(session: AsyncSession | Session, redis_client=None) -> float:
        """Fetch reseller wallet balance with 30-second Redis TTL caching to circuit-break empty balances."""
        cache_key = "ghstore:cache:reseller_balance"
        r = redis_client or BatStoreProductRepository._redis
        if r is not None:
            try:
                cached = await r.get(cache_key)
                if cached is not None:
                    return float(cached)
            except Exception:
                pass

        try:
            me_info = await BatStoreService.me(session)
            raw_b = me_info.get("wallet_balance")
            if raw_b is None:
                raw_b = me_info.get("wallet", {}).get("balance", 0.0)
            bal = float(raw_b or 0.0)
            if r is not None:
                try:
                    await r.setex(cache_key, 30, str(bal))
                except Exception:
                    pass
            return bal
        except Exception as e:
            logging.warning("Failed to fetch reseller balance for circuit breaker: %s", e)
            return 9999.0

    @staticmethod
    async def ping_health(session: AsyncSession | Session) -> bool:
        """Fast ping to check if upstream reseller API is responsive."""
        try:
            resp = await BatStoreService._request("GET", "/api/reseller/me", session, timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    async def get_order(session: AsyncSession | Session, order_id: int) -> dict:
        resp = await BatStoreService._request("GET", f"/api/reseller/orders/{order_id}", session)
        if resp.status_code != 200:
            raise BatStoreAPIError(f"GET /orders/{order_id} {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if not data.get("success"):
            raise BatStoreAPIError(f"GET /orders/{order_id} failed: {resp.text[:200]}")
        return data

    @staticmethod
    def extract_delivery_goods(order_data: dict) -> list[str]:
        """Extract delivered goods from a BatStore order response."""
        order = order_data.get("order") or order_data
        items = order.get("items") or []
        goods = []
        for it in items:
            value = it.get("value") or it.get("data") or str(it)
            goods.append(value)
        return goods

    @staticmethod
    def validate_delivery_goods(items: list) -> bool:
        """Dead-on-Arrival (DOA) pre-delivery validation.

        Ensures delivered credentials are non-empty and well-formed.
        """
        if not items:
            return False
        for it in items:
            val = str(it.get("value") if isinstance(it, dict) else it).strip()
            if len(val) < 3:
                return False
            lower = val.lower()
            if any(bad in lower for bad in ("error", "invalid", "revoked", "suspended", "null", "undefined")):
                return False
        return True

    @staticmethod
    def get_order_reseller_status(order_data: dict) -> str:
        """Map reseller order status to our internal status.

        Returns: 'completed', 'failed', or 'pending'.
        """
        order = order_data.get("order") or order_data
        status = (order.get("status") or "").lower()
        if status in ("completed", "delivered", "fulfilled"):
            return "completed"
        if status in ("failed", "cancelled", "expired", "refunded"):
            return "failed"
        return "pending"

    # ------------------------------------------------------------------ margin

    @staticmethod
    def compute_sell_price(cost: float,
                           global_percent: float,
                           global_fixed: float,
                           margin_type: str | None = None,
                           margin_value: float | None = None,
                           global_type: str | None = None) -> float:
        """Compute the selling price for a product.

        Per-product margin_type wins over the global defaults:
          percent     : cost * (1 + margin_value/100) + global_fixed
          fixed       : cost + margin_value
          fixed_price : margin_value (exact price)
          tiered      : tiered percentage markup depending on cost bands
        Falls back to global percent/fixed/tiered when no per-product type is set.
        """
        mtype = (margin_type or "").lower() if margin_type else ""
        mval = margin_value if margin_value is not None else 0.0
        # A per-product value is only meaningful when non-zero.
        has_value = mval != 0
        if mtype == MarginType.FIXED_PRICE:
            # exact fixed sell price; require an explicit value else global
            return round(mval, 2) if has_value else round(cost * (1 + global_percent / 100.0) + global_fixed, 2)
        if mtype == MarginType.FIXED:
            # flat USD adder when set, else global percent
            return round(cost + mval, 2) if has_value else round(cost * (1 + global_percent / 100.0) + global_fixed, 2)
        if mtype == MarginType.PERCENT:
            # per-product percent when set, else global percent
            pct = mval if has_value else global_percent
            return round(cost * (1 + pct / 100.0) + global_fixed, 2)
        if mtype == "tiered" or (not mtype and (global_type or "").lower() == "tiered"):
            tier_pct = BatStoreService.compute_tiered_margin(cost, global_percent)
            return round(cost * (1 + tier_pct / 100.0) + global_fixed, 2)
        # no per-product type -> global defaults
        return round(cost * (1 + global_percent / 100.0) + global_fixed, 2)

    @staticmethod
    def compute_tiered_margin(cost: float, fallback_percent: float = 20.0) -> float:
        """Dynamic margin curve: higher margin for cheaper items, lower for high-ticket items."""
        if cost <= 2.0:
            return 50.0
        elif cost <= 10.0:
            return 40.0
        elif cost <= 50.0:
            return 25.0
        elif cost > 50.0:
            return 15.0
        return fallback_percent
    @staticmethod
    def get_volume_discount(quantity: int) -> float:
        """Wholesale bulk discount matrix: 1-4: 0%, 5-9: 7%, 10+: 15%."""
        qty = int(quantity or 1)
        if qty >= 10:
            return 15.0
        elif qty >= 5:
            return 7.0
        return 0.0

    @staticmethod
    async def _global_margin(session: AsyncSession | Session) -> tuple[float, float, str]:
        percent = float(await ConfigService.get(session, "MARGIN_PERCENT",
                                                env_fallback=config.MARGIN_PERCENT, default="0") or 0)
        fixed = float(await ConfigService.get(session, "MARGIN_FIXED",
                                              env_fallback=config.MARGIN_FIXED, default="0") or 0)
        mtype = await ConfigService.get(session, "DEFAULT_MARGIN_TYPE",
                                        env_fallback=config.DEFAULT_MARGIN_TYPE, default="percent")
        return percent, fixed, (mtype or "percent")

    # ------------------------------------------------------------------- sync

    @staticmethod
    async def sync_catalog(session: AsyncSession | Session) -> tuple[int, int]:
        """Pull /products and upsert rows in batstore_products.

        Excludes the synthetic API-test product. Recomputes sell_price_usd based
        on each product's stored margin config (falling back to global margin for
        new products). Returns (created, updated) counts.
        """
        global_percent, global_fixed, global_type = await BatStoreService._global_margin(session)
        products = await BatStoreService.list_products(session)
        ar_desc_map: dict[int, str] = {}
        try:
            ar_products = await BatStoreService.list_products(session, lang="ar")
            for arp in ar_products:
                if arp.get("id") and arp.get("description"):
                    ar_desc_map[int(arp["id"])] = arp["description"]
        except Exception as e:
            logging.warning("Failed to fetch Arabic descriptions from reseller API: %s", e)
        rules = await CustomEmojiService.get_rules(session)
        created = 0
        updated = 0
        restocked_products: list[tuple[int, str]] = []
        price_spikes: list[tuple[int, str, float, float]] = []
        kept_ids: list[int] = []
        for p in products:
            pid = int(p["id"])
            if pid == API_TEST_PRODUCT_ID or p.get("api_test"):
                continue
            kept_ids.append(pid)
            cost = float(p.get("price_usd") or 0.0)
            product_name = p.get("name") or f"Product {pid}"
            existing = await BatStoreProductRepository.get_by_product_id(pid, session)
            detected_emoji, detected_custom_id = CustomEmojiService.detect_icon(product_name, rules)
            if existing is None:
                dto = BatStoreProductDTO(
                    product_id=pid,
                    name=product_name,
                    description=clean_tg_emojis(p.get("description")),
                    description_ar=clean_tg_emojis(ar_desc_map.get(pid)),
                    emoji=p.get("emoji") or detected_emoji,
                    custom_emoji_id=detected_custom_id,
                    image_url=p.get("image_url"),
                    cost_usd=cost,
                    standard_price_usd=p.get("standard_price_usd"),
                    delivery_type=p.get("delivery_type"),
                    stock=p.get("stock"),
                    warranty_days=p.get("warranty_days"),
                    margin_type=None,
                    margin_value=None,
                    category=auto_categorize(product_name),
                    sell_price_usd=BatStoreService.compute_sell_price(
                        cost, global_percent, global_fixed, None, None, global_type),
                    hidden=False,
                )
                await BatStoreProductRepository.create(dto, session)
                created += 1
            else:
                old_stock = existing.stock
                new_stock = p.get("stock")
                was_out_of_stock = (
                    (existing.delivery_type == "stock" and not (old_stock and old_stock > 0)) or
                    (old_stock is not None and old_stock <= 0)
                )
                now_in_stock = new_stock is not None and new_stock > 0
                if was_out_of_stock and now_in_stock:
                    restocked_products.append((pid, p.get("name") or existing.name))

                is_price_spike = False
                if existing.cost_usd and existing.cost_usd > 0:
                    delta_ratio = (cost - existing.cost_usd) / existing.cost_usd
                    if delta_ratio >= 0.10:
                        delta_pct = round(delta_ratio * 100.0, 1)
                        from models.price_audit import ProductPriceAudit
                        session.add(ProductPriceAudit(
                            product_id=pid,
                            product_name=p.get("name") or existing.name,
                            old_cost=existing.cost_usd,
                            new_cost=cost,
                            delta_percent=delta_pct
                        ))
                        if delta_ratio >= 0.30:
                            is_price_spike = True
                            price_spikes.append((pid, p.get("name") or existing.name, existing.cost_usd, cost))
                sell = BatStoreService.compute_sell_price(
                    cost, global_percent, global_fixed, existing.margin_type,
                    existing.margin_value if existing.margin_type != MarginType.FIXED_PRICE
                    else existing.margin_value, global_type)
                cat = existing.category if existing.category else auto_categorize(product_name)
                upd = BatStoreProductDTO(
                    id=existing.id,
                    product_id=pid,
                    name=p.get("name") or existing.name,
                    description=clean_tg_emojis(p.get("description") or existing.description),
                    description_ar=clean_tg_emojis(ar_desc_map.get(pid) or existing.description_ar),
                    custom_emoji_id=existing.custom_emoji_id or detected_custom_id,
                    image_url=p.get("image_url") or existing.image_url,
                    cost_usd=cost,
                    standard_price_usd=p.get("standard_price_usd"),
                    delivery_type=p.get("delivery_type") or existing.delivery_type,
                    stock=p.get("stock"),
                    warranty_days=p.get("warranty_days") or existing.warranty_days,
                    margin_type=existing.margin_type,
                    margin_value=existing.margin_value,
                    category=cat,
                    sell_price_usd=sell,
                    hidden=True if is_price_spike else existing.hidden,
                )
                await BatStoreProductRepository.update(upd, session)
                updated += 1
        await BatStoreProductRepository.delete_absent(kept_ids, session)
        await session_commit(session)
        for restocked_pid, restocked_name in restocked_products:
            try:
                await RestockNotificationService.notify_batstore_product_restocked(
                    batstore_product_id=restocked_pid,
                    product_name=restocked_name,
                    session=session
                )
            except Exception as e:
                logging.error("Failed to notify restocked product %s: %s", restocked_pid, e)
        if restocked_products:
            await session_commit(session)
        for spike_pid, spike_name, old_c, new_c in price_spikes:
            try:
                pct = ((new_c - old_c) / old_c) * 100
                await NotificationService.send_error_to_admins(
                    f"price_spike_{spike_pid}",
                    f"⚠️ <b>Price Spike Circuit Breaker Triggered!</b>\n\n"
                    f"• <b>Product:</b> {spike_name} (ID: <code>{spike_pid}</code>)\n"
                    f"• <b>Old Cost:</b> ${old_c:.2f}\n"
                    f"• <b>New Cost:</b> ${new_c:.2f} (+{pct:.0f}%)\n\n"
                    f"<i>This product was automatically hidden from the storefront to prevent loss. Review margins in SQLAdmin or the Reseller Menu.</i>",
                    None
                )
            except Exception as e:
                logging.error("Failed to notify admin of price spike for %s: %s", spike_pid, e)
            await session_commit(session)
        try:
            from bot import broadcast_sse_event
            broadcast_sse_event("stock_update", {"updated": updated, "created": created})
        except Exception:
            pass
        return created, updated
