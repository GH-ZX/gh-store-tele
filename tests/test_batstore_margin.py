import pytest
from services.batstore import BatStoreService


class TestComputeSellPrice:
    """BatStoreService.compute_sell_price — the core margin logic."""

    def test_global_percent_only(self):
        result = BatStoreService.compute_sell_price(
            cost=10.0, global_percent=20, global_fixed=0)
        assert result == 12.0

    def test_global_percent_with_fixed_adder(self):
        result = BatStoreService.compute_sell_price(
            cost=10.0, global_percent=20, global_fixed=2.5)
        assert result == 14.5

    def test_global_fixed_only(self):
        result = BatStoreService.compute_sell_price(
            cost=10.0, global_percent=0, global_fixed=3.0)
        assert result == 13.0

    def test_per_product_percent(self):
        result = BatStoreService.compute_sell_price(
            cost=10.0, global_percent=20, global_fixed=0,
            margin_type="percent", margin_value=50)
        assert result == 15.0

    def test_per_product_fixed(self):
        result = BatStoreService.compute_sell_price(
            cost=10.0, global_percent=20, global_fixed=0,
            margin_type="fixed", margin_value=5.0)
        assert result == 15.0

    def test_per_product_fixed_price(self):
        result = BatStoreService.compute_sell_price(
            cost=10.0, global_percent=20, global_fixed=0,
            margin_type="fixed_price", margin_value=25.0)
        assert result == 25.0

    def test_per_product_fixed_price_zero_falls_back_to_global(self):
        result = BatStoreService.compute_sell_price(
            cost=10.0, global_percent=20, global_fixed=0,
            margin_type="fixed_price", margin_value=0)
        assert result == 12.0

    def test_no_margin(self):
        result = BatStoreService.compute_sell_price(
            cost=10.0, global_percent=0, global_fixed=0)
        assert result == 10.0

    def test_rounding(self):
        result = BatStoreService.compute_sell_price(
            cost=9.99, global_percent=15, global_fixed=0)
        assert result == round(9.99 * 1.15, 2)

    def test_zero_cost(self):
        result = BatStoreService.compute_sell_price(
            cost=0.0, global_percent=20, global_fixed=1.0)
        assert result == 1.0
