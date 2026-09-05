"""Cent-safe reseller prices and gross profit, before fees and operating expenses."""
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal(0)


def money(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid_price") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("invalid_price")
    return amount


def normalize_coupon_type(value) -> str | None:
    """Accept CouponType enum, PERCENT/PERCENTAGE and FIXED/CURRENCY aliases."""
    name = getattr(value, "value", value)
    text = str(name or "").upper()
    if text in ("PERCENT", "PERCENTAGE", "PERCENTAGE_COUPON"):
        return "PERCENTAGE"
    if text in ("FIXED", "CURRENCY", "FIXED_COUPON"):
        return "FIXED"
    return None


def _quantity(value) -> int:
    if isinstance(value, bool):
        raise ValueError("invalid_quantity")
    quantity = int(value)
    if quantity < 1:
        raise ValueError("invalid_quantity")
    return quantity


def price_lines(lines, discount_pct=0, coupon_type=None, coupon_value=0):
    """Price (unit sell, unit cost, quantity, volume %) lines; cap every discount.

    Return cent-exact line totals and whether the requested reduction was limited.
    A below-cost list price is unavailable, never silently increased at checkout.
    Fixed/cart coupon reductions share the remaining margins, not supplier costs.
    """
    totals, floors = [], []
    limited = False
    vip = min(money(discount_pct), Decimal(100))
    for sell, cost, quantity, volume in lines:
        quantity = _quantity(quantity)
        base = (money(sell) * quantity).quantize(CENT, rounding=ROUND_HALF_UP)
        floor = max(CENT, (money(cost) * quantity).quantize(CENT, rounding=ROUND_CEILING))
        if base < floor:
            raise ValueError("price_unavailable")
        discounted = base
        for pct in (vip, min(money(volume), Decimal(100))):
            discounted -= (discounted * pct / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        limited |= discounted < floor
        totals.append(max(floor, discounted))
        floors.append(floor)
    if not totals:
        raise ValueError("empty_cart")
    subtotal = sum(totals, ZERO)
    coupon_kind = normalize_coupon_type(coupon_type)
    requested = money(coupon_value) if coupon_kind else ZERO
    if coupon_kind == "PERCENTAGE":
        requested = subtotal * requested / 100
    requested = requested.quantize(CENT, rounding=ROUND_HALF_UP)
    margins = [total - floor for total, floor in zip(totals, floors)]
    capacity = sum(margins, ZERO)
    reduction = min(requested, capacity)
    limited |= requested > capacity
    if reduction > 0:
        # Largest-remainder allocation preserves both the exact payable total and
        # each line's floor, independent of float rounding or cart line ordering.
        shares = [reduction * margin / capacity for margin in margins]
        cuts = [share.quantize(CENT, rounding=ROUND_FLOOR) for share in shares]
        remainder = int((reduction - sum(cuts, ZERO)) / CENT)
        ranking = sorted(range(len(shares)), key=lambda i: shares[i] - cuts[i], reverse=True)
        for i in ranking[:remainder]:
            cuts[i] += CENT
        totals = [total - cut for total, cut in zip(totals, cuts)]
    return totals, limited


def order_cost(details) -> Decimal:
    """Order snapshots store unit cost_usd and line-total sell_usd."""
    return sum((money(d.get("cost_usd") or 0) * money(d.get("quantity") or 1)
                for d in (details or [])), ZERO)


def externally_paid(order) -> bool:
    details = getattr(order, "details", None)
    if isinstance(order, dict):
        details = order.get("details")
    return any(isinstance(d, dict) and d.get("payment_method") == "external" for d in (details or []))
