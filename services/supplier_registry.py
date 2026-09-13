"""Supplier capability registry and adapters.

Replaces name-based branching (``if supplier == "g2bulk": ...``) with a
registry of provider adapters, each declaring which of the six standard
supplier capabilities it implements:

- ``catalog``  — sync upstream catalogue into the local product table
- ``quote``    — fetch a live price / availability for a product
- ``purchase`` — place an order upstream and normalize the response
- ``status``   — query upstream order status
- ``cancel``   — void / refund an upstream order (unsupported by all today)
- ``balance``  — read the supplier wallet balance (cached)

Callers ask the registry for an adapter and use ``supports(...)`` /
``require(...)`` instead of string comparison on supplier names.
"""
from abc import ABC
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from services.batstore import BatStoreService, BatStoreAPIError, BatStoreOutOfStockError
from services.prodseller import ProdSellerService, ProdSellerAPIError, ProdSellerOutOfStockError
from services.g2bulk import G2BulkService, G2BulkAPIError, G2BulkOutOfStockError


class SupplierCapability(str, Enum):
    """Standard operations a supplier adapter may expose."""

    CATALOG = "catalog"
    QUOTE = "quote"
    PURCHASE = "purchase"
    STATUS = "status"
    CANCEL = "cancel"
    BALANCE = "balance"


class SupplierCapabilityUnsupported(Exception):
    """Raised when an adapter is asked to run an operation it does not support."""

    def __init__(self, supplier: str, capability: str):
        self.supplier = supplier
        self.capability = capability
        super().__init__(f"Supplier '{supplier}' does not support capability '{capability}'")


class SupplierAdapter(ABC):
    """Base class describing the capability surface of one upstream provider."""

    name: str = ""
    display_name: str = ""
    badge: str = ""
    alternate_badge: str = ""
    capabilities: frozenset[SupplierCapability] = frozenset()
    out_of_stock_error: type[Exception] | None = None
    api_error: type[Exception] | None = None

    def supports(self, capability: SupplierCapability | str) -> bool:
        return capability in self.capabilities

    def require(self, capability: SupplierCapability | str) -> None:
        if not self.supports(capability):
            raise SupplierCapabilityUnsupported(self.name, str(capability))

    def is_out_of_stock(self, exc: Exception) -> bool:
        return self.out_of_stock_error is not None and isinstance(exc, self.out_of_stock_error)

    async def sync_catalog(self, session: AsyncSession | Session) -> tuple[int, int]:
        self.require(SupplierCapability.CATALOG)
        raise NotImplementedError

    async def quote(self, session: AsyncSession | Session, product, quantity: int = 1) -> dict[str, Any]:
        self.require(SupplierCapability.QUOTE)
        raise NotImplementedError

    async def purchase(
        self,
        session: AsyncSession | Session,
        product,
        quantity: int = 1,
        customer_reference: str | None = None,
        idempotency_key: str | None = None,
        extra_params: dict | None = None,
        alternate_badge: bool = False,
    ) -> dict[str, Any]:
        self.require(SupplierCapability.PURCHASE)
        raise NotImplementedError

    async def order_status(self, session: AsyncSession | Session, order) -> dict[str, Any]:
        self.require(SupplierCapability.STATUS)
        raise NotImplementedError

    async def cancel(self, session: AsyncSession | Session, order) -> dict[str, Any]:
        self.require(SupplierCapability.CANCEL)
        raise NotImplementedError

    async def get_cached_balance(
        self,
        session: AsyncSession | Session,
        redis_client=None,
        force_refresh: bool = False,
    ) -> float:
        self.require(SupplierCapability.BALANCE)
        raise NotImplementedError


class BatStoreAdapter(SupplierAdapter):
    name = "batstore"
    display_name = "BatStore / VenteBot"
    badge = "سيرفر 1 (BatStore)"
    alternate_badge = "سيرفر 1 (BatStore - بديل)"
    capabilities = frozenset({
        SupplierCapability.CATALOG,
        SupplierCapability.QUOTE,
        SupplierCapability.PURCHASE,
        SupplierCapability.STATUS,
        SupplierCapability.BALANCE,
    })
    out_of_stock_error = BatStoreOutOfStockError
    api_error = BatStoreAPIError

    async def sync_catalog(self, session: AsyncSession | Session) -> tuple[int, int]:
        return await BatStoreService.sync_catalog(session)

    async def quote(self, session: AsyncSession | Session, product, quantity: int = 1) -> dict[str, Any]:
        product_id = int(getattr(product, "product_id", None) or 0)
        key_override = getattr(product, "reseller_key_override", None)
        return await BatStoreService.quote(session, product_id, quantity, key_override=key_override)

    async def purchase(
        self,
        session: AsyncSession | Session,
        product,
        quantity: int = 1,
        customer_reference: str | None = None,
        idempotency_key: str | None = None,
        extra_params: dict | None = None,
        alternate_badge: bool = False,
    ) -> dict[str, Any]:
        bat_resp = await BatStoreService.place_order(
            session, product.product_id, quantity,
            customer_reference=customer_reference, idempotency_key=idempotency_key
        )
        ext_ref = bat_resp.get("order", {}).get("id") or bat_resp.get("order_id")
        items = bat_resp.get("order", {}).get("items") or []
        goods = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
        return {
            "supplier": self.name,
            "server_badge": self.alternate_badge if alternate_badge else self.badge,
            "external_order_ref": str(ext_ref) if ext_ref else None,
            "goods": goods,
            "raw_order": bat_resp,
        }

    async def order_status(self, session: AsyncSession | Session, order) -> dict[str, Any]:
        raw = await BatStoreService.get_order(session, int(order.get("external_order_ref") or 0))
        return {
            "status": BatStoreService.get_order_reseller_status(raw),
            "raw": raw,
        }

    async def get_cached_balance(
        self,
        session: AsyncSession | Session,
        redis_client=None,
        force_refresh: bool = False,
    ) -> float:
        return await BatStoreService.get_cached_reseller_balance(session, redis_client, force_refresh=force_refresh)


class ProdSellerAdapter(SupplierAdapter):
    name = "prodseller"
    display_name = "ProdSeller"
    badge = "سيرفر 2 (ProdSeller)"
    alternate_badge = "سيرفر 2 (ProdSeller - بديل)"
    capabilities = frozenset({
        SupplierCapability.CATALOG,
        SupplierCapability.PURCHASE,
        SupplierCapability.STATUS,
        SupplierCapability.BALANCE,
    })
    out_of_stock_error = ProdSellerOutOfStockError
    api_error = ProdSellerAPIError

    async def sync_catalog(self, session: AsyncSession | Session) -> tuple[int, int]:
        return await ProdSellerService.sync_catalog(session)

    async def purchase(
        self,
        session: AsyncSession | Session,
        product,
        quantity: int = 1,
        customer_reference: str | None = None,
        idempotency_key: str | None = None,
        extra_params: dict | None = None,
        alternate_badge: bool = False,
    ) -> dict[str, Any]:
        mongo_id = getattr(product, "reseller_key_override", None) or str(product.product_id)
        order_resp = await ProdSellerService.place_order(
            session, mongo_id, quantity, idempotency_key=idempotency_key
        )
        goods = ProdSellerService.extract_delivery_goods(order_resp)
        return {
            "supplier": self.name,
            "server_badge": self.alternate_badge if alternate_badge else self.badge,
            "external_order_ref": str(order_resp.get("orderId") or order_resp.get("id") or ""),
            "goods": goods,
            "raw_order": order_resp,
        }

    async def order_status(self, session: AsyncSession | Session, order) -> dict[str, Any]:
        raw = await ProdSellerService.get_order(session, str(order.get("external_order_ref") or ""))
        return {
            "status": ProdSellerService.get_order_reseller_status(raw),
            "raw": raw,
        }

    async def get_cached_balance(
        self,
        session: AsyncSession | Session,
        redis_client=None,
        force_refresh: bool = False,
    ) -> float:
        return await ProdSellerService.get_cached_balance(session, redis_client, force_refresh=force_refresh)


class G2BulkAdapter(SupplierAdapter):
    name = "g2bulk"
    display_name = "G2Bulk Games"
    badge = "سيرفر 3 (G2Bulk Games)"
    games_badge = "سيرفر 3 (G2Bulk Games)"
    voucher_badge = "سيرفر 3 (G2Bulk Vouchers)"
    alternate_badge = "سيرفر 3 (G2Bulk - بديل)"
    capabilities = frozenset({
        SupplierCapability.CATALOG,
        SupplierCapability.PURCHASE,
        SupplierCapability.STATUS,
        SupplierCapability.BALANCE,
    })
    out_of_stock_error = G2BulkOutOfStockError
    api_error = G2BulkAPIError

    async def sync_catalog(self, session: AsyncSession | Session) -> tuple[int, int]:
        return await G2BulkService.sync_catalog(session)

    async def purchase(
        self,
        session: AsyncSession | Session,
        product,
        quantity: int = 1,
        customer_reference: str | None = None,
        idempotency_key: str | None = None,
        extra_params: dict | None = None,
        alternate_badge: bool = False,
    ) -> dict[str, Any]:
        extra_params = extra_params or {}
        delivery_type = getattr(product, "delivery_type", "voucher") or "voucher"
        games_badge = self.alternate_badge if alternate_badge else self.games_badge
        voucher_badge = self.alternate_badge if alternate_badge else self.voucher_badge

        if delivery_type in ("direct_topup", "game_recharge"):
            game_code = getattr(product, "reseller_key_override", None)
            if not game_code and getattr(product, "extra_meta", None):
                game_code = product.extra_meta.get("game_code")
            game_code = game_code or "aoem"

            catalogue_name = extra_params.get("catalogue_name")
            if not catalogue_name and getattr(product, "extra_meta", None):
                items = product.extra_meta.get("items", [])
                if items:
                    catalogue_name = items[0].get("name")
            catalogue_name = catalogue_name or "Standard"

            player_id = str(extra_params.get("player_id") or "").strip()
            server_id = extra_params.get("server_id")
            charname = extra_params.get("charname")

            order_resp = await G2BulkService.create_game_order(
                session, game_code, catalogue_name, player_id,
                server_id=server_id, charname=charname,
                remark=customer_reference, idempotency_key=idempotency_key
            )
            upstream_id = str(order_resp.get("order_id") or "")
            status_val = str(order_resp.get("status") or "PENDING").upper()
            goods: list[str] = []
            return {
                "supplier": self.name,
                "server_badge": games_badge,
                "external_order_ref": f"g2b-game-{upstream_id}" if upstream_id else None,
                "goods": goods,
                "raw_order": order_resp,
                "status": status_val,
            }

        v_prod_id = extra_params.get("selected_item_id")
        if not v_prod_id and getattr(product, "extra_meta", None):
            items = product.extra_meta.get("items", [])
            if items:
                v_prod_id = items[0].get("id")
        if not v_prod_id:
            v_prod_id = getattr(product, "reseller_key_override", None) or product.product_id

        order_resp = await G2BulkService.purchase_voucher(
            session, int(v_prod_id), quantity=quantity, idempotency_key=idempotency_key
        )
        upstream_id = str(order_resp.get("order_id") or "")
        goods = G2BulkService.extract_delivery_goods(order_resp)
        status_val = str(order_resp.get("status") or ("COMPLETED" if goods else "PENDING")).upper()
        return {
            "supplier": self.name,
            "server_badge": voucher_badge,
            "external_order_ref": f"g2b-vouch-{upstream_id}" if upstream_id else None,
            "goods": goods,
            "raw_order": order_resp,
            "status": status_val,
        }

    async def order_status(self, session: AsyncSession | Session, order) -> dict[str, Any]:
        external_ref = str(order.get("external_order_ref") or "")
        upstream_id = external_ref.split("-", 2)[-1] if external_ref.startswith("g2b-") else external_ref
        if external_ref.startswith("g2b-game-"):
            raw = await G2BulkService.get_game_order_status(upstream_id, session)
        else:
            raw = await G2BulkService.get_delivery(upstream_id, session)
        return {"status": str(raw.get("status") or "PENDING").upper(), "raw": raw}

    async def get_cached_balance(
        self,
        session: AsyncSession | Session,
        redis_client=None,
        force_refresh: bool = False,
    ) -> float:
        return await G2BulkService.get_cached_balance(session, redis_client, force_refresh=force_refresh)


class SupplierRegistry:
    """Registry mapping canonical supplier names to their capability adapters."""

    _adapters: dict[str, SupplierAdapter] = {}

    @classmethod
    def register(cls, adapter: SupplierAdapter) -> None:
        cls._adapters[adapter.name] = adapter

    @classmethod
    def get(cls, supplier_name: str | None) -> SupplierAdapter:
        key = (supplier_name or "batstore").strip().lower()
        return cls._adapters.get(key) or cls._adapters["batstore"]

    @classmethod
    def all(cls) -> list[SupplierAdapter]:
        return list(cls._adapters.values())

    @classmethod
    def names(cls) -> frozenset[str]:
        return frozenset(cls._adapters.keys())

    @classmethod
    def has(cls, supplier_name: str | None) -> bool:
        return (supplier_name or "").strip().lower() in cls._adapters

    @classmethod
    def capabilities_of(cls, supplier_name: str | None) -> frozenset[SupplierCapability]:
        return cls.get(supplier_name).capabilities


SupplierRegistry.register(BatStoreAdapter())
SupplierRegistry.register(ProdSellerAdapter())
SupplierRegistry.register(G2BulkAdapter())