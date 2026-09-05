from decimal import Decimal

import pytest

from services.sale_pricing import externally_paid, normalize_coupon_type, order_cost, price_lines


class _Order:
    def __init__(self, details):
        self.details = details


def test_vip_and_volume_capped_at_cost():
    (total,), limited = price_lines([(10.0, 9.0, 1, 0)], discount_pct=50.0)
    assert total == Decimal("9.00")
    assert limited is True


def test_below_cost_list_price_unavailable():
    with pytest.raises(ValueError, match="price_unavailable"):
        price_lines([(5.0, 9.0, 1, 0)])


def test_fixed_coupon_shares_margin_and_sums_to_total():
    totals, limited = price_lines(
        [(10.0, 8.0, 1, 0), (20.0, 18.0, 1, 0)],
        coupon_type="FIXED", coupon_value=3.0)
    assert sum(totals, Decimal(0)) == Decimal("27.00")
    assert all(t >= f for t, f in zip(totals, [Decimal("8.00"), Decimal("18.00")]))
    assert limited is False


def test_coupon_larger_than_margin_is_limited():
    totals, limited = price_lines([(10.0, 9.0, 1, 0)], coupon_type="FIXED", coupon_value=5.0)
    assert totals == [Decimal("9.00")]
    assert limited is True


def test_percent_coupon_alias_and_order_cost():
    (total,), _ = price_lines([(20.0, 10.0, 1, 0)], coupon_type="PERCENT", coupon_value=10.0)
    assert total == Decimal("18.00")
    assert normalize_coupon_type("currency") == "FIXED"
    assert order_cost([{"cost_usd": 9.0, "quantity": 2}]) == Decimal("18.0")


def test_externally_paid_marks_manual_sales_only():
    assert externally_paid(_Order([{"payment_method": "external"}])) is True
    assert externally_paid(_Order([{"admin_gift": True}])) is False
    assert externally_paid(_Order([])) is False
