import pytest
from types import SimpleNamespace

from services.batstore import BatStoreService, BatStoreAPIError


class TestExtractDeliveryGoods:

    def test_extracts_values_from_items(self):
        order_data = {
            "order": {
                "items": [
                    {"value": "user:pass1"},
                    {"value": "user:pass2"},
                ]
            }
        }
        goods = BatStoreService.extract_delivery_goods(order_data)
        assert goods == ["user:pass1", "user:pass2"]

    def test_extracts_data_field_fallback(self):
        order_data = {
            "order": {
                "items": [
                    {"data": "key123"},
                ]
            }
        }
        goods = BatStoreService.extract_delivery_goods(order_data)
        assert goods == ["key123"]

    def test_stringifies_item_when_no_value_or_data(self):
        order_data = {
            "order": {
                "items": [
                    {"id": 1, "name": "test"},
                ]
            }
        }
        goods = BatStoreService.extract_delivery_goods(order_data)
        assert len(goods) == 1
        assert "test" in goods[0]

    def test_empty_items(self):
        order_data = {"order": {"items": []}}
        assert BatStoreService.extract_delivery_goods(order_data) == []

    def test_no_order_key_uses_top_level(self):
        order_data = {
            "items": [{"value": "abc"}]
        }
        goods = BatStoreService.extract_delivery_goods(order_data)
        assert goods == ["abc"]


class TestGetOrderResellerStatus:

    @pytest.mark.parametrize("status,expected", [
        ("completed", "completed"),
        ("delivered", "completed"),
        ("fulfilled", "completed"),
        ("COMPLETED", "completed"),
        ("failed", "failed"),
        ("cancelled", "failed"),
        ("expired", "failed"),
        ("refunded", "failed"),
        ("pending", "pending"),
        ("processing", "pending"),
        ("", "pending"),
    ])
    def test_status_mapping(self, status, expected):
        order_data = {"order": {"status": status}}
        assert BatStoreService.get_order_reseller_status(order_data) == expected

    def test_no_status_field(self):
        order_data = {"order": {}}
        assert BatStoreService.get_order_reseller_status(order_data) == "pending"

    def test_uses_order_key_if_present(self):
        order_data = {"order": {"status": "delivered"}, "status": "pending"}
        assert BatStoreService.get_order_reseller_status(order_data) == "completed"

    def test_falls_back_to_top_level(self):
        order_data = {"status": "completed"}
        assert BatStoreService.get_order_reseller_status(order_data) == "completed"
