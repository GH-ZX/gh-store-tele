from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from repositories.product import ProductRepository
from services.multi_supplier import MultiSupplierService
from services.batstore import BatStoreOutOfStockError


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


def test_match_tokens_normalization():
    assert ProductRepository.match_tokens("Canva Pro") == frozenset({"canva", "pro"})
    assert ProductRepository.match_tokens("canva-pro (Pro)") == frozenset({"canva", "pro"})
    assert ProductRepository.match_tokens("ChatGPT Plus / 1 month") == frozenset({"chatgpt", "plus", "1", "month"})
    assert ProductRepository.match_tokens("") == frozenset()
    assert ProductRepository.match_tokens(None) == frozenset()


def test_token_overlap_scoring():
    a = frozenset({"canva", "pro"})
    assert ProductRepository.token_overlap(a, frozenset({"canva", "pro", "personal"})) == pytest.approx(2 / 3)
    assert ProductRepository.token_overlap(a, frozenset({"netflix"})) == 0.0
    assert ProductRepository.token_overlap(frozenset(), a) == 0.0


@pytest.mark.asyncio
async def test_find_approved_equivalent_both_directions():
    rows = [
        SimpleNamespace(product_id=100, equivalent_product_id=200),
        SimpleNamespace(product_id=300, equivalent_product_id=200),
    ]
    with patch("repositories.product.session_execute", AsyncMock(return_value=_ScalarResult(rows))):
        assert await ProductRepository.find_approved_equivalent(100, AsyncMock()) == 200
        assert await ProductRepository.find_approved_equivalent(200, AsyncMock()) == 100
        assert await ProductRepository.find_approved_equivalent(300, AsyncMock()) == 200
        assert await ProductRepository.find_approved_equivalent(999, AsyncMock()) is None
        assert await ProductRepository.find_approved_equivalent(None, AsyncMock()) is None


@pytest.mark.asyncio
async def test_find_alternate_prefers_approved_pair_over_name():
    candidate = SimpleNamespace(
        id=2, product_id=2123456, name="Hugely Different Title", custom_name="Hugely Different Title",
        supplier="prodseller", hidden=False, stock=5,
    )
    with patch("repositories.product.ProductRepository.find_approved_equivalent", AsyncMock(return_value=2123456)), \
         patch("repositories.product.ProductRepository.get_by_product_id", AsyncMock(return_value=candidate)):
        result = await ProductRepository.find_alternate_in_stock(
            "Canva Pro", "prodseller", AsyncMock(), product_id=91432
        )
    assert result is not None
    assert result.product_id == 2123456


@pytest.mark.asyncio
async def test_find_alternate_approved_pair_requires_target_supplier():
    candidate = SimpleNamespace(
        id=2, product_id=2123456, name="Canva Pro", custom_name="Canva Pro",
        supplier="batstore", hidden=False, stock=5,
    )
    with patch("repositories.product.ProductRepository.find_approved_equivalent", AsyncMock(return_value=2123456)), \
         patch("repositories.product.ProductRepository.get_by_product_id", AsyncMock(return_value=candidate)):
        result = await ProductRepository.find_alternate_in_stock(
            "Canva Pro", "prodseller", AsyncMock(), product_id=91432
        )
    assert result is None


@pytest.mark.asyncio
async def test_find_alternate_token_match_exact():
    row = SimpleNamespace(
        id=1, product_id=2123456, name="Canva Pro (Invite)", custom_name="Canva Pro Invite",
        supplier="prodseller", hidden=False, stock=5,
    )
    with patch("repositories.product.ProductRepository.find_approved_equivalent", AsyncMock(return_value=None)), \
         patch("repositories.product.session_execute", AsyncMock(return_value=_ScalarResult([row]))):
        result = await ProductRepository.find_alternate_in_stock(
            "canva-pro", "prodseller", AsyncMock(), product_id=91432
        )
    assert result is not None
    assert result.product_id == 2123456


@pytest.mark.asyncio
async def test_find_alternate_rejects_low_token_overlap():
    row = SimpleNamespace(
        id=1, product_id=2123456, name="Netflix 4 Screens", custom_name="Netflix 4 Screens",
        supplier="prodseller", hidden=False, stock=5,
    )
    with patch("repositories.product.ProductRepository.find_approved_equivalent", AsyncMock(return_value=None)), \
         patch("repositories.product.session_execute", AsyncMock(return_value=_ScalarResult([row]))):
        result = await ProductRepository.find_alternate_in_stock(
            "Netflix 1 Screen", "prodseller", AsyncMock(), product_id=91432
        )
    assert result is None


@pytest.mark.asyncio
async def test_find_alternate_skips_primary_self():
    row = SimpleNamespace(
        id=1, product_id=91432, name="Canva Pro", custom_name="Canva Pro",
        supplier="prodseller", hidden=False, stock=5,
    )
    with patch("repositories.product.ProductRepository.find_approved_equivalent", AsyncMock(return_value=None)), \
         patch("repositories.product.session_execute", AsyncMock(return_value=_ScalarResult([row]))):
        result = await ProductRepository.find_alternate_in_stock(
            "Canva Pro", "prodseller", AsyncMock(), product_id=91432
        )
    assert result is None


@pytest.mark.asyncio
async def test_failover_passes_product_id_to_alternate_lookup():
    product = SimpleNamespace(
        product_id=91432, name="Canva Pro", custom_name="Canva Pro", supplier="batstore",
    )
    alternate = SimpleNamespace(
        product_id=2123456, name="Canva Pro", custom_name="Canva Pro",
        supplier="prodseller", reseller_key_override="6a316a7b1777fc2347835653",
    )
    find_alt = AsyncMock(return_value=alternate)
    with patch("services.batstore.BatStoreService.place_order",
               AsyncMock(side_effect=BatStoreOutOfStockError("OOS"))), \
         patch("repositories.batstore_product.BatStoreProductRepository.find_alternate_in_stock", find_alt), \
         patch("services.prodseller.ProdSellerService.place_order",
               AsyncMock(return_value={"orderId": "ps_alt", "deliveredKey": "KEY-P"})):
        res = await MultiSupplierService.place_order_with_failover(AsyncMock(), product)
    assert res["supplier"] == "prodseller"
    assert res["server_badge"] == "سيرفر 2 (ProdSeller - بديل)"
    assert find_alt.await_args.kwargs.get("product_id") == 91432