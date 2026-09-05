import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from services.prodseller import (
    ProdSellerService,
    ProdSellerAPIError,
    ProdSellerOutOfStockError,
)
from services.multi_supplier import MultiSupplierService
from services.batstore import BatStoreOutOfStockError


def test_generate_product_id_deterministic():
    mongo_id = "6a2fda51035a6d898f2106fe"
    id1 = ProdSellerService.generate_product_id(mongo_id)
    id2 = ProdSellerService.generate_product_id(mongo_id)
    assert id1 == id2
    assert 2000000 <= id1 < 2900000


def test_generate_product_id_uniqueness():
    id_a = ProdSellerService.generate_product_id("6a2fda51035a6d898f2106fe")
    id_b = ProdSellerService.generate_product_id("6a2fdb4f035a6d898f2106ff")
    assert id_a != id_b


def test_extract_delivery_goods():
    order_data = {
        "deliveredKey": "KEY-1234-ABCD",
        "deliveredKeys": ["KEY-1234-ABCD", "KEY-5678-EFGH"],
    }
    goods = ProdSellerService.extract_delivery_goods(order_data)
    assert len(goods) == 2
    assert goods[0] == "KEY-1234-ABCD"
    assert goods[1] == "KEY-5678-EFGH"


@pytest.mark.asyncio
async def test_get_routing_strategy_default():
    mock_session = AsyncMock()
    with patch("services.config.ConfigService.get", AsyncMock(return_value="auto_cheapest")):
        strat = await MultiSupplierService.get_routing_strategy(mock_session)
        assert strat == "auto_cheapest"


@pytest.mark.asyncio
async def test_place_order_prodseller_success():
    mock_session = AsyncMock()
    product = SimpleNamespace(
        id=1,
        product_id=2123456,
        name="Canva Pro",
        clean_name="Canva Pro",
        cost_usd=0.5,
        sell_price_usd=1.0,
        supplier="prodseller",
        reseller_key_override="6a316a7b1777fc2347835653",
    )

    mock_resp = {
        "orderId": "ps_order_999",
        "deliveredKey": "CANVA-PRO-INVITE-URL",
        "status": "completed",
    }
    with patch("services.prodseller.ProdSellerService.place_order", AsyncMock(return_value=mock_resp)):
        res = await MultiSupplierService.place_order_with_failover(
            mock_session, product, quantity=1, customer_reference="test-ref"
        )
        assert res["supplier"] == "prodseller"
        assert res["external_order_ref"] == "ps_order_999"
        assert res["goods"] == ["CANVA-PRO-INVITE-URL"]


@pytest.mark.asyncio
async def test_place_order_prodseller_failover_to_batstore():
    mock_session = AsyncMock()
    product = SimpleNamespace(
        id=1,
        product_id=2123456,
        name="Canva Pro",
        clean_name="Canva Pro",
        cost_usd=0.5,
        sell_price_usd=1.0,
        supplier="prodseller",
        reseller_key_override="6a316a7b1777fc2347835653",
    )
    alternate_batstore = SimpleNamespace(
        id=2,
        product_id=155,
        name="Canva Pro 1 Year",
        cost_usd=0.6,
        sell_price_usd=1.2,
        supplier="batstore",
        stock=5,
    )

    with patch("services.prodseller.ProdSellerService.place_order", AsyncMock(side_effect=ProdSellerOutOfStockError("Out of stock"))):
        with patch("repositories.batstore_product.BatStoreProductRepository.find_alternate_in_stock", AsyncMock(return_value=alternate_batstore)):
            with patch("services.batstore.BatStoreService.place_order", AsyncMock(return_value={
                "order": {"id": "bat_order_777", "items": [{"value": "BAT-KEY-111"}]}
            })):
                res = await MultiSupplierService.place_order_with_failover(
                    mock_session, product, quantity=1, customer_reference="test-failover"
                )
                assert res["supplier"] == "batstore"
                assert "بديل" in res["server_badge"]
                assert res["external_order_ref"] == "bat_order_777"
                assert res["goods"] == ["BAT-KEY-111"]


@pytest.mark.asyncio
async def test_place_order_batstore_failover_to_prodseller():
    mock_session = AsyncMock()
    product = SimpleNamespace(
        id=1,
        product_id=155,
        name="Canva Pro",
        clean_name="Canva Pro",
        cost_usd=0.6,
        sell_price_usd=1.2,
        supplier="batstore",
    )
    alternate_prodseller = SimpleNamespace(
        id=2,
        product_id=2123456,
        name="Canva Pro 2 yrs",
        cost_usd=0.5,
        sell_price_usd=1.0,
        supplier="prodseller",
        reseller_key_override="6a316a7b1777fc2347835653",
        stock=10,
    )

    with patch("services.batstore.BatStoreService.place_order", AsyncMock(side_effect=BatStoreOutOfStockError("Out of stock"))):
        with patch("repositories.batstore_product.BatStoreProductRepository.find_alternate_in_stock", AsyncMock(return_value=alternate_prodseller)):
            with patch("services.prodseller.ProdSellerService.place_order", AsyncMock(return_value={
                "orderId": "ps_failover_888",
                "deliveredKey": "PRODSELLER-FALLBACK-KEY",
            })):
                res = await MultiSupplierService.place_order_with_failover(
                    mock_session, product, quantity=1, customer_reference="test-failover-2"
                )
                assert res["supplier"] == "prodseller"
                assert "بديل" in res["server_badge"]
                assert res["external_order_ref"] == "ps_failover_888"
                assert res["goods"] == ["PRODSELLER-FALLBACK-KEY"]
