"""Durable, idempotent checkout shared by storefront entry points."""
import hashlib
import json
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from models.order import Order, OrderDTO
from models.user import User
from repositories.order import OrderRepository
from repositories.product import ProductRepository
from repositories.user import UserRepository
from services.batstore import BatStoreService
from services.config import ConfigService
from services.sale_pricing import compute_reseller_price, money, price_lines
from services.user import get_vip_tier_info


def resolve_variant(product, supplied: dict) -> dict | None:
    """Resolve both selectors together; never forward unpriced client variants."""
    items = (getattr(product, "extra_meta", None) or {}).get("items") or []
    selected_id = supplied.get("selected_item_id")
    name = str(supplied.get("catalogue_name") or "").strip()
    if getattr(product, "supplier", "") != "g2bulk":
        if selected_id is not None or name:
            raise ValueError("invalid_variant")
        return None
    if not items:
        if selected_id is not None or name:
            raise ValueError("invalid_variant")
        return None
    matches = [item for item in items
               if (selected_id is None or str(item.get("id")) == str(selected_id))
               and (not name or str(item.get("name") or "").casefold() == name.casefold())]
    if selected_id is None and not name:
        # An omitted selector is safe only for an unambiguous product.
        if len(items) != 1:
            raise ValueError("variant_required")
    if len(matches) != 1:
        raise ValueError("invalid_variant")
    chosen = dict(matches[0])
    if chosen.get("stock") is not None and money(chosen["stock"]) <= 0:
        raise ValueError("out_of_stock")
    return chosen


def normalize_checkout(body: dict, cart: bool) -> dict:
    if not isinstance(body, dict):
        raise ValueError("invalid_json")
    raw_items = body.get("items") if cart else [body]
    if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 20:
        raise ValueError("invalid_cart")
    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError("invalid_item")
        pid, qty = raw.get("product_id"), raw.get("quantity", 1)
        if isinstance(pid, bool) or isinstance(qty, bool):
            raise ValueError("invalid_quantity")
        if not str(pid).isdigit() or not str(qty).isdigit():
            raise ValueError("invalid_quantity")
        pid, qty = int(pid), int(qty)
        if pid < 1 or not 1 <= qty <= (20 if cart else 10):
            raise ValueError("invalid_quantity")
        item = {"product_id": pid, "quantity": qty}
        for field in ("selected_item_id", "catalogue_name", "player_id", "server_id", "charname"):
            value = raw.get(field)
            if value is not None:
                if not isinstance(value, (str, int)) or isinstance(value, bool):
                    raise ValueError("invalid_parameters")
                value = str(value).strip()
                if len(value) > 200:
                    raise ValueError("invalid_parameters")
                if value:
                    item[field] = value
        items.append(item)
    coupon = body.get("coupon_code") or ""
    if not isinstance(coupon, str) or len(coupon) > 100:
        raise ValueError("invalid_coupon")
    return {"items": items, "coupon_code": coupon.strip(), "cart": cart}


async def priced_product(product, supplied, user, session):
    chosen = resolve_variant(product, supplied)
    cost = money(chosen["cost"] if chosen and chosen.get("cost") is not None else product.cost_usd or 0)
    retail = money(chosen["price"] if chosen and chosen.get("price") is not None else product.sell_price_usd)
    if bool(getattr(user, "is_reseller", False)):
        if chosen:
            price = money(chosen.get("reseller_price") or retail)
        else:
            margin = await ConfigService.get(session, "GLOBAL_RESELLER_MARGIN_PERCENT", default="8.0")
            price = money(compute_reseller_price(cost, retail,
                getattr(product, "reseller_price_usd", None),
                getattr(product, "reseller_margin_pct", None), margin))
    else:
        price = retail
    return chosen, cost, price


class CheckoutService:
    @staticmethod
    async def reserve(tg_id: int, body: dict, key: str, session, *, cart=False):
        """Lock wallet, deduplicate, and commit order plus debit in one transaction."""
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
            raise HTTPException(400, "idempotency_key_required")
        try:
            payload = normalize_checkout(body, cart)
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        user = (await session.execute(select(User).where(User.telegram_id == tg_id).with_for_update())).scalar_one_or_none()
        if user is None:
            raise HTTPException(404, "user_not_found")
        if user.is_banned:
            raise HTTPException(403, "account_banned")
        existing = (await session.execute(select(Order).where(Order.telegram_id == tg_id, Order.checkout_key == key))).scalar_one_or_none()
        if existing:
            if existing.request_fingerprint != fingerprint:
                raise HTTPException(409, "idempotency_key_conflict")
            await session.commit()
            return existing, False
        lines, price_inputs = [], []
        for supplied in payload["items"]:
            product = await ProductRepository.get_by_product_id(supplied["product_id"], session)
            if not product or product.hidden:
                raise HTTPException(400, "product_unavailable")
            try:
                variant, cost, price = await priced_product(product, supplied, user, session)
                if product.stock is not None and money(product.stock) < supplied["quantity"] and not variant:
                    raise ValueError("out_of_stock")
            except (ValueError, TypeError) as exc:
                raise HTTPException(400, str(exc)) from exc
            params = {k: supplied[k] for k in ("player_id", "server_id", "charname") if k in supplied}
            if variant:
                params.update(selected_item_id=variant.get("id"), catalogue_name=variant.get("name"))
            direct = product.delivery_type in ("direct_topup", "game_recharge")
            if direct:
                if supplied["quantity"] != 1:
                    raise HTTPException(400, "direct_topup_quantity_one")
                fields = (product.extra_meta or {}).get("required_fields") or ["userid"]
                for upstream, local in (("userid", "player_id"), ("serverid", "server_id"), ("charname", "charname")):
                    if upstream in fields and not params.get(local):
                        raise HTTPException(400, "missing_" + local)
            from services.product_spec import ProductSpecParser
            guide = ProductSpecParser.extract_clean_instructions(product.description, getattr(product, "description_ar", None), product.name)
            meta = product.extra_meta or {}
            lines.append({
                "product_id": product.product_id, "name": product.name,
                "quantity": supplied["quantity"], "cost_usd": float(cost),
                "delivery_type": product.delivery_type, "supplier": product.supplier,
                "status": "created", "delivery_goods": [], "extra_params": params,
                **params,
                "product_snapshot": {"product_id": product.product_id, "name": product.name,
                    "supplier": product.supplier, "delivery_type": product.delivery_type,
                    "reseller_key_override": product.reseller_key_override, "extra_meta": meta},
                "warranty_days": product.warranty_days or 0,
                "instructions_en": meta.get("instructions_en") or guide.get("steps_en", []),
                "instructions_ar": meta.get("instructions_ar") or guide.get("steps_ar", []),
                "redemption_url": meta.get("redemption_url", ""),
            })
            price_inputs.append((price, cost, supplied["quantity"], BatStoreService.get_volume_discount(supplied["quantity"])))
        from repositories.coupon import CouponRepository
        coupon = await CouponRepository.get_by_code(payload["coupon_code"], session) if payload["coupon_code"] else None
        if payload["coupon_code"] and (not coupon or not coupon.is_active):
            raise HTTPException(400, "invalid_coupon")
        _, discount = get_vip_tier_info(user.consume_records or 0, user.custom_discount_pct)
        try:
            totals, _ = price_lines(price_inputs, discount_pct=discount,
                coupon_type=coupon.type if coupon else None, coupon_value=coupon.value if coupon else 0)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        total = float(sum(totals, Decimal(0)))
        for line, amount in zip(lines, totals):
            line["sell_usd"] = float(amount)
        if not await UserRepository.try_debit_balance(tg_id, total, session):
            raise HTTPException(400, "insufficient_balance")
        if coupon and not await CouponRepository.increment_usage(coupon.id, session):
            raise HTTPException(400, "coupon_limit_reached")
        order = await OrderRepository.create(OrderDTO(telegram_id=tg_id, total_sell=total,
            status="created", customer_reference="checkout-" + hashlib.sha256(f"{tg_id}:{key}".encode()).hexdigest()[:32],
            checkout_key=key, request_fingerprint=fingerprint, details=lines), session)
        try:
            await session.commit()
        except IntegrityError:
            # A concurrent identical submission won the unique (telegram_id,
            # checkout_key) insert. Reconcile instead of surfacing a 500.
            await session.rollback()
            existing = (await session.execute(
                select(Order).where(Order.telegram_id == tg_id, Order.checkout_key == key))).scalar_one_or_none()
            if existing is not None and existing.request_fingerprint == fingerprint:
                return existing, False
            raise HTTPException(409, "idempotency_key_conflict")
        return order, True

    @staticmethod
    def response(order):
        lines = order.details or []
        first = lines[0] if lines else {}
        return {"status": "success", "order_id": order.id, "total_paid": order.total_sell,
            "product_name": first.get("name", ""), "quantity": first.get("quantity", 1),
            "items_count": len(lines), "reseller_status": order.status,
            "goods": [good for line in lines for good in line.get("delivery_goods", [])],
            "instructions_en": first.get("instructions_en", []),
            "instructions_ar": first.get("instructions_ar", []),
            "redemption_url": first.get("redemption_url", ""),
            "refunded_amount": sum(float(line.get("sell_usd") or 0) for line in lines if line.get("refund_applied")),
        }
