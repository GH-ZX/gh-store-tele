"""Durable per-item supplier attempts and atomic wallet refunds.

Supplier I/O happens only after committing a submitting claim. A crashed or
ambiguous attempt must be reconciled; it is never blindly purchased again.
"""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select

from models.order import Order
from repositories.user import UserRepository
from services.sale_pricing import externally_paid

TERMINAL = {"completed", "failed", "refunded", "cancelled"}
UNSUBMITTED = {"created", "queued", "pending_supplier_recharge"}


def normalized_details(order):
    details = deepcopy(order.details or [])
    for index, item in enumerate(details):
        item.setdefault("status", "completed" if item.get("delivery_goods") else order.status)
        item.setdefault("customer_reference", f"order-{order.id}-line-{index}")
        item.setdefault("idempotency_key", item["customer_reference"])
        if len(details) == 1:
            item.setdefault("external_order_ref", order.external_order_ref)
            item.setdefault("sell_usd", float(order.total_sell or 0))
        # Only explicit provider metadata identifies a provider. Numeric IDs are
        # not evidence that an order belongs to BatStore.
    return details


def aggregate_status(details):
    states = {item.get("status") for item in details}
    if not states:
        return "requires_manual_review"
    if states == {"completed"}:
        return "completed"
    if states <= {"failed", "refunded", "cancelled"}:
        return "failed"
    if "requires_manual_review" in states:
        return "requires_manual_review"
    if states <= TERMINAL:
        return "partially_completed"
    if states == {"pending_supplier_recharge"}:
        return "pending_supplier_recharge"
    return "pending_fulfillment"


async def locked_order(order_id, session):
    result = await session.execute(select(Order).where(Order.id == order_id)
        .with_for_update().execution_options(populate_existing=True))
    return result.scalar_one_or_none()


class FulfillmentService:
    @staticmethod
    async def transition_item(order_id, index, status, goods, session, *, external_ref=None, supplier=None):
        """Apply one confirmed outcome. Caller commits outcome and refund together."""
        order = await locked_order(order_id, session)
        if order is None:
            return None, False
        details = normalized_details(order)
        if index >= len(details):
            return order, False
        item = details[index]
        if supplier and item.get("supplier") != supplier:
            return order, False
        if external_ref and str(item.get("external_order_ref") or "") != str(external_ref):
            return order, False
        if item.get("status") in TERMINAL:
            return order, False
        if status in {"failed", "cancelled", "refunded"} and not item.get("refund_applied"):
            amount = item.get("sell_usd")
            if amount is None:
                status = "requires_manual_review"
            elif externally_paid(order):
                item["external_refund_required"] = True
            else:
                await UserRepository.refund_balance(order.telegram_id, float(amount), session)
                item["refund_applied"] = True
                item["refund_amount"] = float(amount)
        item["status"] = status
        if goods is not None:
            item["delivery_goods"] = list(goods)
        order.details = details
        order.status = aggregate_status(details)
        await session.flush()
        return order, True

    @staticmethod
    async def fulfill_order(order_id, session):
        from repositories.product import ProductRepository
        from services.multi_supplier import MultiSupplierService
        from services.batstore import BatStoreOutOfStockError
        from services.prodseller import ProdSellerOutOfStockError
        from services.g2bulk import G2BulkOutOfStockError

        order = await locked_order(order_id, session)
        if order is None:
            return None
        count = len(order.details or [])
        await session.commit()
        for index in range(count):
            order = await locked_order(order_id, session)
            details = normalized_details(order)
            item = details[index]
            if item.get("status") not in UNSUBMITTED:
                await session.commit()
                continue
            snapshot = item.get("product_snapshot")
            product = SimpleNamespace(**snapshot) if snapshot else await ProductRepository.get_by_product_id(item.get("product_id"), session)
            if product is None:
                await FulfillmentService.transition_item(order_id, index, "requires_manual_review", None, session)
                await session.commit()
                continue
            item["supplier"] = item.get("supplier") or getattr(product, "supplier", None)
            from services.supplier_registry import SupplierRegistry
            if item["supplier"] not in SupplierRegistry.names():
                item["status"] = "requires_manual_review"
                order.details = details
                order.status = aggregate_status(details)
                await session.commit()
                continue
            item["status"] = "submitting"
            item["submitted_at"] = datetime.now(timezone.utc).isoformat()
            order.details = details
            order.status = aggregate_status(details)
            await session.commit()
            try:
                placed = await MultiSupplierService.place_order_with_failover(
                    session, product, int(item.get("quantity") or 1),
                    customer_reference=item["customer_reference"],
                    idempotency_key=item["idempotency_key"],
                    extra_params=item.get("extra_params") or {},
                )
            except (BatStoreOutOfStockError, ProdSellerOutOfStockError, G2BulkOutOfStockError):
                await session.rollback()
                await FulfillmentService.transition_item(order_id, index, "failed", None, session)
                await session.commit()
                continue
            except Exception:
                await session.rollback()
                await FulfillmentService.transition_item(order_id, index, "requires_manual_review", None, session)
                await session.commit()
                continue
            order = await locked_order(order_id, session)
            details = normalized_details(order)
            current = details[index]
            if current.get("status") in TERMINAL:
                await session.commit()
                continue
            current["supplier"] = placed.get("supplier") or item["supplier"]
            current["external_order_ref"] = placed.get("external_order_ref")
            current["delivery_goods"] = list(placed.get("goods") or [])
            current["server_badge"] = placed.get("server_badge")
            order.details = details
            if len(details) == 1:
                order.external_order_ref = current["external_order_ref"]
            raw_status = str(placed.get("status") or "").lower()
            if raw_status in {"failed", "cancelled", "refunded", "rejected"}:
                status = "failed"
            elif current["delivery_goods"] or raw_status in {"completed", "success", "delivered", "active"}:
                status = "completed"
            elif current["external_order_ref"]:
                status = "pending_fulfillment"
            else:
                status = "requires_manual_review"
            # Flush snapshot before refreshing the locked row in transition_item.
            await session.flush()
            await FulfillmentService.transition_item(order_id, index, status, current["delivery_goods"], session)
            await session.commit()
        return await locked_order(order_id, session)

    @staticmethod
    async def supplier_status(item, session):
        ref = str(item.get("external_order_ref") or "")
        supplier = item.get("supplier")
        if supplier == "batstore":
            from services.batstore import BatStoreService
            data = await BatStoreService.get_order(session, int(ref))
            return BatStoreService.get_order_reseller_status(data), BatStoreService.extract_delivery_goods(data)
        if supplier == "prodseller":
            from services.prodseller import ProdSellerService
            data = await ProdSellerService.get_order(session, ref)
            return ProdSellerService.get_order_reseller_status(data), ProdSellerService.extract_delivery_goods(data)
        if supplier == "g2bulk":
            from services.g2bulk import G2BulkService
            if ref.startswith("g2b-game-"):
                data = await G2BulkService.get_game_order_status(ref.removeprefix("g2b-game-"), session)
                status = str(data.get("order", {}).get("status") or data.get("status") or "").lower()
                return status, ["Game Top-Up Completed Successfully"] if status == "completed" else []
            if ref.startswith("g2b-vouch-"):
                data = await G2BulkService.get_delivery(ref.removeprefix("g2b-vouch-"), session)
                return str(data.get("status") or "").lower(), G2BulkService.extract_delivery_goods(data)
        raise ValueError("Unknown provider or unrecognized supplier order reference")
