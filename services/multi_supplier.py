"""Multi-Supplier Routing & Fulfillment Orchestration Engine.

Coordinates multiple upstream suppliers:
- Server 1: BatStore / VenteBot (api.reseller)
- Server 2: ProdSeller (prodseller.com/v1)

Features:
- Smart Auto-Cheapest routing to maximize profit margins
- Server 1 (BatStore) vs Server 2 (ProdSeller) badges
- Automatic failover if primary server is out of stock
- Live supplier wallet balances monitoring
"""
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from models.batstore_product import BatStoreProduct
from repositories.batstore_product import BatStoreProductRepository
from services.batstore import BatStoreService, BatStoreOutOfStockError, BatStoreAPIError
from services.prodseller import ProdSellerService, ProdSellerOutOfStockError, ProdSellerAPIError
from services.config import ConfigService


class MultiSupplierService:
    ROUTING_AUTO_CHEAPEST = "auto_cheapest"
    ROUTING_BATSTORE_PRIMARY = "batstore_primary"
    ROUTING_PRODSELLER_PRIMARY = "prodseller_primary"

    @staticmethod
    async def get_routing_strategy(session: AsyncSession | Session) -> str:
        """Get the configured supplier routing strategy (default: auto_cheapest)."""
        val = await ConfigService.get(session, "SUPPLIER_ROUTING_STRATEGY", default=MultiSupplierService.ROUTING_AUTO_CHEAPEST)
        return str(val or MultiSupplierService.ROUTING_AUTO_CHEAPEST).strip().lower()

    @staticmethod
    async def sync_all_suppliers(session: AsyncSession | Session) -> dict[str, Any]:
        """Sync catalogs from both BatStore and ProdSeller, tag server badges, and tag duplicate offerings."""
        bat_created, bat_updated = await BatStoreService.sync_catalog(session)
        prod_created, prod_updated = await ProdSellerService.sync_catalog(session)

        # Tag server badges on all active products
        all_products = await BatStoreProductRepository.get_all(session)
        for p in all_products:
            if getattr(p, "supplier", "batstore") == "prodseller":
                p.server_badge = "سيرفر 2 (ProdSeller)"
            else:
                p.supplier = "batstore"
                p.server_badge = "سيرفر 1 (BatStore)"
            await BatStoreProductRepository.update(p, session)

        from db import session_commit
        await session_commit(session)

        return {
            "batstore": {"created": bat_created, "updated": bat_updated},
            "prodseller": {"created": prod_created, "updated": prod_updated},
            "total_products": len(all_products),
        }

    @staticmethod
    async def get_cached_supplier_balance(product: BatStoreProduct, session: AsyncSession | Session, redis_client=None) -> float:
        """Check the cached reseller wallet balance for the specific supplier of this product."""
        supplier = getattr(product, "supplier", "batstore")
        if supplier == "prodseller":
            return await ProdSellerService.get_cached_balance(session, redis_client)
        return await BatStoreService.get_cached_reseller_balance(session, redis_client)

    @staticmethod
    async def place_order_with_failover(
        session: AsyncSession | Session,
        product: BatStoreProduct,
        quantity: int = 1,
        customer_reference: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Place order upstream with the product's supplier.

        If the primary supplier is out of stock, automatically check if an alternate
        server has the product in stock and fail over without dropping the customer order.
        """
        supplier = getattr(product, "supplier", "batstore")

        if supplier == "prodseller":
            mongo_id = getattr(product, "reseller_key_override", None) or str(product.product_id)
            try:
                order_resp = await ProdSellerService.place_order(
                    session, mongo_id, quantity, idempotency_key=idempotency_key
                )
                goods = ProdSellerService.extract_delivery_goods(order_resp)
                return {
                    "supplier": "prodseller",
                    "server_badge": "سيرفر 2 (ProdSeller)",
                    "external_order_ref": str(order_resp.get("orderId") or order_resp.get("id") or ""),
                    "goods": goods,
                    "raw_order": order_resp,
                }
            except ProdSellerOutOfStockError as e:
                logging.warning("ProdSeller out of stock for %s, checking BatStore failover: %s", product.name, e)
                # Attempt failover to BatStore if matching product exists
                alternate = await BatStoreProductRepository.find_alternate_in_stock(
                    product.clean_name or product.name, "batstore", session
                )
                if alternate:
                    logging.info("Auto-failover: Routing to BatStore product #%s", alternate.product_id)
                    alt_resp = await BatStoreService.place_order(
                        session, alternate.product_id, quantity,
                        customer_reference=customer_reference, idempotency_key=idempotency_key
                    )
                    ext_ref = alt_resp.get("order", {}).get("id") or alt_resp.get("order_id")
                    items = alt_resp.get("order", {}).get("items") or []
                    goods = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
                    return {
                        "supplier": "batstore",
                        "server_badge": "سيرفر 1 (BatStore - بديل)",
                        "external_order_ref": str(ext_ref) if ext_ref else None,
                        "goods": goods,
                        "raw_order": alt_resp,
                    }
                raise e

        # Default BatStore supplier
        try:
            bat_resp = await BatStoreService.place_order(
                session, product.product_id, quantity,
                customer_reference=customer_reference, idempotency_key=idempotency_key
            )
            ext_ref = bat_resp.get("order", {}).get("id") or bat_resp.get("order_id")
            items = bat_resp.get("order", {}).get("items") or []
            goods = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
            return {
                "supplier": "batstore",
                "server_badge": "سيرفر 1 (BatStore)",
                "external_order_ref": str(ext_ref) if ext_ref else None,
                "goods": goods,
                "raw_order": bat_resp,
            }
        except BatStoreOutOfStockError as e:
            logging.warning("BatStore out of stock for #%s, checking ProdSeller failover: %s", product.product_id, e)
            # Attempt failover to ProdSeller if matching product exists
            alternate = await BatStoreProductRepository.find_alternate_in_stock(
                product.clean_name or product.name, "prodseller", session
            )
            if alternate and alternate.reseller_key_override:
                logging.info("Auto-failover: Routing to ProdSeller product %s", alternate.reseller_key_override)
                alt_resp = await ProdSellerService.place_order(
                    session, alternate.reseller_key_override, quantity, idempotency_key=idempotency_key
                )
                goods = ProdSellerService.extract_delivery_goods(alt_resp)
                return {
                    "supplier": "prodseller",
                    "server_badge": "سيرفر 2 (ProdSeller - بديل)",
                    "external_order_ref": str(alt_resp.get("orderId") or alt_resp.get("id") or ""),
                    "goods": goods,
                    "raw_order": alt_resp,
                }
            raise e
