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
from services.g2bulk import G2BulkService, G2BulkOutOfStockError, G2BulkAPIError
from services.config import ConfigService

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
        """Sync catalogs from both BatStore and ProdSeller, tag server badges, and tag duplicate offerings."""
        bat_created, bat_updated = await BatStoreService.sync_catalog(session)
        prod_created, prod_updated = await ProdSellerService.sync_catalog(session)
        g2b_created = g2b_updated = 0
        g2b_sync = (await ConfigService.get(session, "G2BULK_SYNC_ENABLED", default="true")).lower() == "true"
        if g2b_sync:
            try:
                g2b_created, g2b_updated = await G2BulkService.sync_catalog(session)
            except Exception as ex_g2b:
                logging.warning("G2Bulk catalog sync error: %s", ex_g2b)

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
            "batstore": {"created": bat_created, "updated": bat_updated},
            "prodseller": {"created": prod_created, "updated": prod_updated},
            "g2bulk": {"created": g2b_created, "updated": g2b_updated},
            "total_products": total_count,
        }

    @staticmethod
    async def get_cached_supplier_balance(product: BatStoreProduct, session: AsyncSession | Session, redis_client=None) -> float:
        """Check the cached reseller wallet balance for the specific supplier of this product."""
        supplier = getattr(product, "supplier", "batstore")
        if supplier == "g2bulk":
            return await G2BulkService.get_cached_balance(session, redis_client)
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
        extra_params: dict | None = None,
    ) -> dict[str, Any]:
        """Place order upstream with the product's supplier.

        If the primary supplier is out of stock, automatically check if an alternate
        server has the product in stock and fail over without dropping the customer order.
        """
        supplier = getattr(product, "supplier", "batstore")

        if supplier == "g2bulk":
            delivery_type = getattr(product, "delivery_type", "voucher") or "voucher"
            if delivery_type in ("direct_topup", "game_recharge"):
                game_code = getattr(product, "reseller_key_override", None)
                if not game_code and getattr(product, "extra_meta", None):
                    game_code = product.extra_meta.get("game_code")
                game_code = game_code or "aoem"

                catalogue_name = (extra_params or {}).get("catalogue_name")
                if not catalogue_name and getattr(product, "extra_meta", None):
                    items = product.extra_meta.get("items", [])
                    if items:
                        catalogue_name = items[0].get("name")
                catalogue_name = catalogue_name or "Standard"

                player_id = str((extra_params or {}).get("player_id") or "").strip()
                server_id = (extra_params or {}).get("server_id")
                charname = (extra_params or {}).get("charname")

                order_resp = await G2BulkService.create_game_order(
                    session, game_code, catalogue_name, player_id,
                    server_id=server_id, charname=charname,
                    remark=customer_reference, idempotency_key=idempotency_key
                )
                upstream_id = str(order_resp.get("order_id") or "")
                status_val = str(order_resp.get("status") or "PENDING").upper()
                # Direct recharge has no voucher payload. Keep it pending until
                # G2Bulk confirms COMPLETED through the status endpoint.
                goods = []
                return {
                    "supplier": "g2bulk",
                    "server_badge": "سيرفر 3 (G2Bulk Games)",
                    "external_order_ref": f"g2b-game-{upstream_id}" if upstream_id else None,
                    "goods": goods,
                    "raw_order": order_resp,
                    "status": status_val,
                }
            else:
                v_prod_id = (extra_params or {}).get("selected_item_id")
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
                    "supplier": "g2bulk",
                    "server_badge": "سيرفر 3 (G2Bulk Vouchers)",
                    "external_order_ref": f"g2b-vouch-{upstream_id}" if upstream_id else None,
                    "goods": goods,
                    "raw_order": order_resp,
                    "status": status_val,
                }

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
                alt_name = getattr(product, "custom_name", None) or product.name
                alternate = await BatStoreProductRepository.find_alternate_in_stock(
                    alt_name, "batstore", session
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
            alt_name = getattr(product, "custom_name", None) or product.name
            alternate = await BatStoreProductRepository.find_alternate_in_stock(
                alt_name, "prodseller", session
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
