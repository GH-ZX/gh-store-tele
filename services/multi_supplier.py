"""Multi-Supplier Routing & Fulfillment Orchestration Engine.

Coordinates multiple upstream suppliers through the capability registry
(``services.supplier_registry``):

- Server 1: BatStore / VenteBot (api.reseller)
- Server 2: ProdSeller (prodseller.com/v1)
- Server 3: G2Bulk (api.g2bulk.com/v1)

Features:
- Smart Auto-Cheapest routing to maximize profit margins
- Automatic failover if the primary supplier is out of stock
- Live supplier wallet balances monitoring
"""
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from models.batstore_product import BatStoreProduct
from repositories.batstore_product import BatStoreProductRepository
from services.config import ConfigService
from services.supplier_registry import (
    SupplierRegistry,
    SupplierCapability,
)

class MultiSupplierService:
    ROUTING_AUTO_CHEAPEST = "auto_cheapest"
    ROUTING_BATSTORE_PRIMARY = "batstore_primary"
    ROUTING_PRODSELLER_PRIMARY = "prodseller_primary"
    ROUTING_G2BULK_PRIMARY = "g2bulk_primary"

    @staticmethod
    async def get_routing_strategy(session: AsyncSession | Session) -> str:
        """Get the configured supplier routing strategy (default: auto_cheapest)."""
        val = await ConfigService.get(session, "SUPPLIER_ROUTING_STRATEGY", default=MultiSupplierService.ROUTING_AUTO_CHEAPEST)
        return str(val or MultiSupplierService.ROUTING_AUTO_CHEAPEST).strip().lower()

    @staticmethod
    async def sync_all_suppliers(session: AsyncSession | Session) -> dict[str, Any]:
        """Sync all registered supplier catalogs and tag server badges."""
        g2b_sync = (await ConfigService.get(session, "G2BULK_SYNC_ENABLED", default="true")).lower() == "true"
        results: dict[str, dict[str, Any]] = {}
        for adapter in SupplierRegistry.all():
            if not adapter.supports(SupplierCapability.CATALOG):
                continue
            if adapter.name == "g2bulk" and not g2b_sync:
                results[adapter.name] = {"created": 0, "updated": 0, "skipped": True}
                continue
            try:
                created, updated = await adapter.sync_catalog(session)
                results[adapter.name] = {"created": created, "updated": updated}
            except Exception as ex:
                logging.warning("%s catalog sync error: %s", adapter.name, ex)
                results[adapter.name] = {"created": 0, "updated": 0, "error": str(ex)}

        from models.batstore_product import BatStoreProduct
        from sqlalchemy import update as _sa_update
        from db import session_execute
        await session_execute(
            _sa_update(BatStoreProduct).where(BatStoreProduct.supplier == "prodseller").values(server_badge="سيرفر 2 (ProdSeller)"),
            session
        )
        await session_execute(
            _sa_update(BatStoreProduct).where(BatStoreProduct.supplier == "g2bulk").values(server_badge="سيرفر 3 (G2Bulk Games)"),
            session
        )
        await session_execute(
            _sa_update(BatStoreProduct).where((BatStoreProduct.supplier == None) | (~BatStoreProduct.supplier.in_(["prodseller", "g2bulk"]))).values(supplier="batstore", server_badge="سيرفر 1 (BatStore)"),
            session
        )
        await BatStoreProductRepository.invalidate_cache()
        from db import session_commit
        await session_commit(session)

        from sqlalchemy import func, select as _sa_select
        total_count = (await session_execute(_sa_select(func.count(BatStoreProduct.id)), session)).scalar() or 0

        try:
            from services.margin_watcher import MarginWatcherService
            await MarginWatcherService.check_and_alert_admin(session)
        except Exception as e:
            logging.warning("Margin watcher check error: %s", e)

        return {
            "batstore": results.get("batstore", {"created": 0, "updated": 0}),
            "prodseller": results.get("prodseller", {"created": 0, "updated": 0}),
            "g2bulk": results.get("g2bulk", {"created": 0, "updated": 0}),
            "total_products": total_count,
        }

    @staticmethod
    async def get_cached_supplier_balance(product: BatStoreProduct, session: AsyncSession | Session, redis_client=None) -> float:
        """Check the cached wallet balance for the product's supplier via its adapter."""
        adapter = SupplierRegistry.get(getattr(product, "supplier", None))
        return await adapter.get_cached_balance(session, redis_client)

    @staticmethod
    async def place_order_with_failover(
        session: AsyncSession | Session,
        product: BatStoreProduct,
        quantity: int = 1,
        customer_reference: str | None = None,
        idempotency_key: str | None = None,
        extra_params: dict | None = None,
    ) -> dict[str, Any]:
        """Place order upstream with the product's supplier.

        If the primary supplier is out of stock, automatically check if an alternate
        server has the product in stock and fail over without dropping the customer order.
        """
        supplier = getattr(product, "supplier", None) or "batstore"
        adapter = SupplierRegistry.get(supplier)

        try:
            return await adapter.purchase(
                session, product, quantity,
                customer_reference=customer_reference,
                idempotency_key=idempotency_key,
                extra_params=extra_params or {},
            )
        except Exception as exc:
            if not adapter.is_out_of_stock(exc):
                raise
            logging.warning("%s out of stock for %s, checking failover: %s", supplier, product.name, exc)

            # Failover partner is the paired stock source (name-based until item 14
            # introduces explicit approved-equivalent offers).
            alt_supplier = "batstore" if supplier == "prodseller" else "prodseller"
            alt_name = getattr(product, "custom_name", None) or product.name
            alternate = await BatStoreProductRepository.find_alternate_in_stock(
                alt_name, alt_supplier, session
            )
            if alternate:
                if alt_supplier == "prodseller" and not alternate.reseller_key_override:
                    raise
                alt_adapter = SupplierRegistry.get(alt_supplier)
                logging.info(
                    "Auto-failover: Routing to %s product #%s", alt_supplier, alternate.product_id
                )
                return await alt_adapter.purchase(
                    session, alternate, quantity,
                    customer_reference=customer_reference,
                    idempotency_key=idempotency_key,
                    extra_params=extra_params or {},
                    alternate_badge=True,
                )
            raise
