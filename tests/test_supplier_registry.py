from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from services.supplier_registry import (
    SupplierCapability,
    SupplierCapabilityUnsupported,
    SupplierRegistry,
)
from services.multi_supplier import MultiSupplierService
from services.prodseller import ProdSellerOutOfStockError
from services.batstore import BatStoreOutOfStockError


def test_registration_and_fallback():
    assert SupplierRegistry.names() == {"batstore", "prodseller", "g2bulk"}
    assert SupplierRegistry.has("prodSeller") is True
    assert SupplierRegistry.has("g2bulk") is True
    assert SupplierRegistry.has("nonexistent") is False
    assert SupplierRegistry.has(None) is False
    assert SupplierRegistry.get("g2bulk").name == "g2bulk"
    assert SupplierRegistry.get("unknown").name == "batstore"


def test_capability_declarations():
    bat = SupplierRegistry.get("batstore")
    assert bat.supports(SupplierCapability.CATALOG)
    assert bat.supports(SupplierCapability.QUOTE)
    assert bat.supports(SupplierCapability.PURCHASE)
    assert bat.supports(SupplierCapability.STATUS)
    assert not bat.supports(SupplierCapability.CANCEL)
    assert bat.supports(SupplierCapability.BALANCE)
    assert SupplierRegistry.capabilities_of("batstore") == bat.capabilities

    prod = SupplierRegistry.get("prodseller")
    assert prod.supports("catalog")
    assert not prod.supports(SupplierCapability.QUOTE)
    assert not prod.supports(SupplierCapability.CANCEL)

    g2 = SupplierRegistry.get("g2bulk")
    assert g2.supports(SupplierCapability.PURCHASE)
    assert g2.supports(SupplierCapability.BALANCE)
    assert not g2.supports(SupplierCapability.QUOTE)
    assert not g2.supports(SupplierCapability.CANCEL)


@pytest.mark.asyncio
async def test_unsupported_capability_raises():
    prod = SupplierRegistry.get("prodseller")
    with pytest.raises(SupplierCapabilityUnsupported):
        await prod.quote(AsyncMock(), SimpleNamespace(product_id=1), 1)

    bat = SupplierRegistry.get("batstore")
    with pytest.raises(SupplierCapabilityUnsupported):
        await bat.cancel(AsyncMock(), {})


@pytest.mark.asyncio
async def test_batstore_purchase_shape():
    product = SimpleNamespace(product_id=123, name="Canva Pro", supplier="batstore")
    mock_resp = {"order": {"id": "bs_1", "items": [{"value": "KEY1"}]}}
    with patch("services.batstore.BatStoreService.place_order", AsyncMock(return_value=mock_resp)):
        res = await MultiSupplierService.place_order_with_failover(AsyncMock(), product, quantity=1)
    assert res["supplier"] == "batstore"
    assert res["server_badge"] == "سيرفر 1 (BatStore)"
    assert res["external_order_ref"] == "bs_1"
    assert res["goods"] == ["KEY1"]


@pytest.mark.asyncio
async def test_prodseller_purchase_shape():
    product = SimpleNamespace(
        product_id=2123456, name="Canva Pro", supplier="prodseller",
        reseller_key_override="6a316a7b1777fc2347835653",
    )
    mock_resp = {"orderId": "ps_1", "deliveredKey": "K1"}
    with patch("services.prodseller.ProdSellerService.place_order", AsyncMock(return_value=mock_resp)):
        res = await MultiSupplierService.place_order_with_failover(AsyncMock(), product)
    assert res["supplier"] == "prodseller"
    assert res["server_badge"] == "سيرفر 2 (ProdSeller)"
    assert res["external_order_ref"] == "ps_1"


@pytest.mark.asyncio
async def test_g2bulk_game_purchase_shape():
    product = SimpleNamespace(
        product_id=7, name="MLBB 86", custom_name="MLBB 86", supplier="g2bulk",
        delivery_type="game_recharge", reseller_key_override="mlbb",
        extra_meta={"game_code": "mlbb", "items": [{"name": "86 Diamonds"}]},
    )
    mock_resp = {"order_id": 42, "status": "PENDING"}
    with patch("services.g2bulk.G2BulkService.create_game_order", AsyncMock(return_value=mock_resp)):
        res = await MultiSupplierService.place_order_with_failover(
            AsyncMock(), product, quantity=1,
            extra_params={"player_id": "123456", "server_id": "2001", "charname": "P"},
        )
    assert res["supplier"] == "g2bulk"
    assert res["server_badge"] == "سيرفر 3 (G2Bulk Games)"
    assert res["external_order_ref"] == "g2b-game-42"
    assert res["status"] == "PENDING"
    assert res["goods"] == []


@pytest.mark.asyncio
async def test_g2bulk_voucher_purchase_shape():
    product = SimpleNamespace(
        product_id=8, name="Pubg Voucher", custom_name="Pubg Voucher", supplier="g2bulk",
        delivery_type="voucher", reseller_key_override="90012",
        extra_meta={"items": [{"id": 90012}]},
    )
    mock_resp = {"order_id": 43, "status": "COMPLETED", "delivery_items": [{"code": "G2B-VCH"}]}
    with patch("services.g2bulk.G2BulkService.purchase_voucher", AsyncMock(return_value=mock_resp)):
        res = await MultiSupplierService.place_order_with_failover(AsyncMock(), product)
    assert res["supplier"] == "g2bulk"
    assert res["server_badge"] == "سيرفر 3 (G2Bulk Vouchers)"
    assert res["external_order_ref"] == "g2b-vouch-43"
    assert res["goods"] == ["G2B-VCH"]


@pytest.mark.asyncio
async def test_failover_prodseller_to_batstore():
    product = SimpleNamespace(
        product_id=2123456, name="Canva Pro", custom_name="Canva Pro",
        supplier="prodseller", reseller_key_override="mongo1",
    )
    alternate = SimpleNamespace(
        product_id=91234, name="Canva Pro", custom_name="Canva Pro",
        supplier="batstore", reseller_key_override=None,
    )
    bat_resp = {"order": {"id": "bs_fail", "items": [{"value": "KEY-B"}]}}
    with patch("services.prodseller.ProdSellerService.place_order",
               AsyncMock(side_effect=ProdSellerOutOfStockError("OOS"))), \
         patch("repositories.batstore_product.BatStoreProductRepository.find_alternate_in_stock",
               AsyncMock(return_value=alternate)), \
         patch("services.batstore.BatStoreService.place_order", AsyncMock(return_value=bat_resp)):
        res = await MultiSupplierService.place_order_with_failover(AsyncMock(), product)
    assert res["supplier"] == "batstore"
    assert res["server_badge"] == "سيرفر 1 (BatStore - بديل)"
    assert res["external_order_ref"] == "bs_fail"
    assert res["goods"] == ["KEY-B"]


@pytest.mark.asyncio
async def test_failover_batstore_to_prodseller():
    product = SimpleNamespace(
        product_id=91234, name="Canva Pro", custom_name="Canva Pro", supplier="batstore",
    )
    alternate = SimpleNamespace(
        product_id=2123456, name="Canva Pro", custom_name="Canva Pro",
        supplier="prodseller", reseller_key_override="6a316a7b1777fc2347835653",
    )
    mock_resp = {"orderId": "ps_fail", "deliveredKey": "KEY-P"}
    with patch("services.batstore.BatStoreService.place_order",
               AsyncMock(side_effect=BatStoreOutOfStockError("OOS"))), \
         patch("repositories.batstore_product.BatStoreProductRepository.find_alternate_in_stock",
               AsyncMock(return_value=alternate)), \
         patch("services.prodseller.ProdSellerService.place_order", AsyncMock(return_value=mock_resp)):
        res = await MultiSupplierService.place_order_with_failover(AsyncMock(), product)
    assert res["supplier"] == "prodseller"
    assert res["server_badge"] == "سيرفر 2 (ProdSeller - بديل)"
    assert res["external_order_ref"] == "ps_fail"


@pytest.mark.asyncio
async def test_failover_batstore_to_prodseller_rejects_without_key_override():
    product = SimpleNamespace(product_id=91234, name="Canva Pro", custom_name="Canva Pro", supplier="batstore")
    alternate = SimpleNamespace(
        product_id=2123456, name="Canva Pro", custom_name="Canva Pro",
        supplier="prodseller", reseller_key_override=None,
    )
    with patch("services.batstore.BatStoreService.place_order",
               AsyncMock(side_effect=BatStoreOutOfStockError("OOS"))), \
         patch("repositories.batstore_product.BatStoreProductRepository.find_alternate_in_stock",
               AsyncMock(return_value=alternate)):
        with pytest.raises(BatStoreOutOfStockError):
            await MultiSupplierService.place_order_with_failover(AsyncMock(), product)


@pytest.mark.asyncio
async def test_failover_no_alternate_reraises():
    product = SimpleNamespace(product_id=5, name="X", custom_name="X", supplier="batstore")
    with patch("services.batstore.BatStoreService.place_order",
               AsyncMock(side_effect=BatStoreOutOfStockError("OOS"))), \
         patch("repositories.batstore_product.BatStoreProductRepository.find_alternate_in_stock",
               AsyncMock(return_value=None)):
        with pytest.raises(BatStoreOutOfStockError):
            await MultiSupplierService.place_order_with_failover(AsyncMock(), product)


@pytest.mark.asyncio
async def test_non_oos_error_not_failed_over():
    product = SimpleNamespace(product_id=5, name="X", custom_name="X", supplier="batstore")
    find_alt = AsyncMock()
    with patch("services.batstore.BatStoreService.place_order",
               AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("repositories.batstore_product.BatStoreProductRepository.find_alternate_in_stock", find_alt):
        with pytest.raises(RuntimeError):
            await MultiSupplierService.place_order_with_failover(AsyncMock(), product)
    find_alt.assert_not_awaited()


@pytest.mark.asyncio
async def test_balance_dispatch_via_adapter():
    product = SimpleNamespace(supplier="g2bulk")
    with patch("services.g2bulk.G2BulkService.get_cached_balance", AsyncMock(return_value=150.0)):
        bal = await MultiSupplierService.get_cached_supplier_balance(product, AsyncMock())
    assert bal == 150.0

    product_bat = SimpleNamespace(supplier="batstore")
    with patch("services.batstore.BatStoreService.get_cached_reseller_balance", AsyncMock(return_value=99.0)):
        bal_bat = await MultiSupplierService.get_cached_supplier_balance(product_bat, AsyncMock())
    assert bal_bat == 99.0


@pytest.mark.asyncio
async def test_sync_all_suppliers_skips_disabled_g2bulk():
    with patch("services.config.ConfigService.get", AsyncMock(return_value="false")), \
         patch("services.batstore.BatStoreService.sync_catalog", AsyncMock(return_value=(3, 1))), \
         patch("services.prodseller.ProdSellerService.sync_catalog", AsyncMock(return_value=(2, 0))), \
         patch("db.session_execute", AsyncMock()), \
         patch("db.session_commit", AsyncMock()), \
         patch("repositories.batstore_product.BatStoreProductRepository.invalidate_cache", AsyncMock()):
        res = await MultiSupplierService.sync_all_suppliers(AsyncMock())
    assert res["batstore"] == {"created": 3, "updated": 1}
    assert res["prodseller"] == {"created": 2, "updated": 0}
    assert res["g2bulk"] == {"created": 0, "updated": 0, "skipped": True}


@pytest.mark.asyncio
async def test_sync_all_suppliers_contains_catalog_errors():
    with patch("services.config.ConfigService.get", AsyncMock(return_value="true")), \
         patch("services.batstore.BatStoreService.sync_catalog",
               AsyncMock(side_effect=RuntimeError("upstream"))), \
         patch("services.prodseller.ProdSellerService.sync_catalog", AsyncMock(return_value=(0, 0))), \
         patch("services.g2bulk.G2BulkService.sync_catalog", AsyncMock(return_value=(0, 0))), \
         patch("db.session_execute", AsyncMock()), \
         patch("db.session_commit", AsyncMock()), \
         patch("repositories.batstore_product.BatStoreProductRepository.invalidate_cache", AsyncMock()):
        res = await MultiSupplierService.sync_all_suppliers(AsyncMock())
    assert res["batstore"]["created"] == 0
    assert "error" in res["batstore"]